"""
合同管理API路由
"""
import logging
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import date

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.models.contract import Contract
from app.schemas.contract import (
    ContractCreate, ContractUpdate, ContractResponse, ContractDetailResponse, ContractWithPaymentsResponse,
    ContractFormCreate,
)
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user, require_role
from app.core.permissions import Role, is_admin, can_delete_contract
from app.models.user import User
from app.services.contract_service import ContractService
from app.services.file_analyzer import FileAnalyzer
from app.utils.file_utils import resolve_file_path
from app.config import settings

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_contracts(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=500, description="每页数量"),
    status: Optional[str] = Query(None, description="合同状态"),
    customer_id: Optional[int] = Query(None, description="客户ID（单个）"),
    customer_ids: Optional[str] = Query(None, description="客户ID列表，逗号分隔（如 1,3,5）"),
    customer_name: Optional[str] = Query(None, description="客户名称"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    date_from: Optional[date] = Query(None, description="签订日期起始"),
    date_to: Optional[date] = Query(None, description="签订日期结束"),
    include: Optional[str] = Query(
        None,
        description='附加返回内容；目前仅支持 "payments"——开启后每个合同返回 payments 流水明细，供台账视图使用。',
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同列表"""
    # 合同对所有角色全部可见（admin/income/expense），不再按 sales_person_id 过滤
    sales_person_id = None

    # 解析 customer_ids
    parsed_customer_ids: Optional[List[int]] = None
    if customer_ids:
        parsed_customer_ids = [int(cid.strip()) for cid in customer_ids.split(",") if cid.strip()]

    # 解析 include 标志（逗号分隔，目前只识别 payments）
    include_set = {x.strip() for x in (include or "").split(",") if x.strip()}
    include_payments = "payments" in include_set

    # 角色 → payment 类型过滤（DB 层下推；与 GET /payments/contract/{id} 一致）
    #   income → 只看 income 流水；expense → 只看 expense 流水；admin → 都看
    if include_payments and current_user.role == Role.INCOME:
        payment_type_filter = "income"
    elif include_payments and current_user.role == Role.EXPENSE:
        payment_type_filter = "expense"
    else:
        payment_type_filter = None

    items, total = ContractService.get_contracts(
        db=db,
        page=page,
        per_page=per_page,
        status=status,
        customer_id=customer_id,
        customer_ids=parsed_customer_ids,
        customer_name=customer_name,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        sales_person_id=sales_person_id,
        include_payments=include_payments,
        payment_type_filter=payment_type_filter,
    )

    response_schema = ContractWithPaymentsResponse if include_payments else ContractResponse
    return PaginatedResponse(
        items=[response_schema.model_validate(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.post("/analyze")
def analyze_contract_file(
    payload: dict,
    current_user: User = Depends(require_role("admin", "income")),
    db: Session = Depends(get_db),
):
    """表单通道 · 步骤1：分析已上传的合同文件，返回 AI 结构化解析结果。

    与 Agent 通道的区别：纯分析，不建合同；前端拿到结果后进入预览步骤，
    用户确认后再调 POST /contracts 建合同。

    FileAnalyzer.analyze(purpose="contract") 会顺带做 hash 去重检测（需传 db），
    命中时返回 duplicate_detected=True + existing_contract，前端据此终止流程。
    """
    file_id = payload.get("file_id")
    if not file_id:
        raise HTTPException(status_code=400, detail="缺少 file_id")

    file_path = resolve_file_path(file_id, current_user.id)
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在或已过期，请重新上传")

    # 同步阻塞调用（内部走 VL 模型，图片型文件可能 10-30s）；前端需展示 loading
    result = FileAnalyzer.analyze(
        file_path=file_path,
        file_name=Path(file_path).name,
        purpose="contract",
        db=db,
        user_id=current_user.id,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "文件分析失败"))

    return result


@router.post("", response_model=ContractResponse)
def create_contract_via_form(
    payload: ContractFormCreate,
    current_user: User = Depends(require_role("admin", "income")),
    db: Session = Depends(get_db),
):
    """表单通道 · 步骤2：根据预览确认的字段 + AI 解析结果创建合同。

    流程：自动生成合同编号 → total_amount 兜底 → 建 Contract 主记录
    → persist_contract_file_and_meta（复制源文件到正式目录 + 写 contract_data/text/confidence）。
    失败回滚已建合同（hash 重复等）。
    """
    contract_number = ContractService.generate_contract_number()

    # total_amount 兜底：表单传入优先，否则从 contract_data 取（AI 提取值）
    total_amount = payload.total_amount
    if total_amount is None:
        raw = payload.contract_data.get("total_amount") if payload.contract_data else None
        if raw is None:
            raise HTTPException(status_code=400, detail="缺少合同金额，请手动填写")
        try:
            total_amount = Decimal(str(raw))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="合同金额格式非法")

    # 构造 ContractCreate（contract_number 后端生成、status 固定 active）
    contract_create = ContractCreate(
        contract_number=contract_number,
        title=payload.title,
        business_type=payload.business_type,
        business_description=payload.business_description,
        customer_id=payload.customer_id,
        currency=payload.currency,
        total_amount=total_amount,
        signed_date=payload.signed_date,
        start_date=payload.start_date,
        end_date=payload.end_date,
        remarks=payload.remarks,
        wechat_group=payload.wechat_group,
        contract_text=payload.contract_text,
        # original_file_path 是 NOT NULL，先用占位（必填），下方共享方法会覆盖
        original_file_path=f"agent_upload/{payload.file_id}",
        file_hash=None,
        status="active",
    )

    try:
        contract = ContractService.create_contract(
            db=db,
            contract_data=contract_create,
            sales_person_id=current_user.id,
        )
        # 复制源文件 + 写 AI 元数据（与 Agent 通道共用）
        contract = ContractService.persist_contract_file_and_meta(
            db=db,
            contract=contract,
            file_id=payload.file_id,
            user_id=current_user.id,
            contract_data=payload.contract_data,
            contract_text=payload.contract_text,
            confidence=payload.confidence,
            source="form",
        )
    except FileNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return contract


@router.get("/{contract_id}", response_model=ContractDetailResponse)
def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同详情"""
    contract = ContractService.get_contract_detail(db, contract_id)

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )

    # 填充 customer_name
    if contract.customer_id:
        from app.models.customer import Customer
        customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
        contract.customer_name = customer.name if customer else None

    # 合同详情对所有角色可见，不再按 sales_person_id 校验

    return contract


@router.get("/{contract_id}/file")
def download_contract_file(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载/预览合同原文件"""
    contract = ContractService.get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # 合同文件对所有角色可见，不再按 sales_person_id 校验

    if not contract.original_file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同文件不存在")

    file_path = Path(settings.CONTRACT_UPLOAD_DIR) / contract.original_file_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同文件已丢失")

    # 根据扩展名设置 Content-Type
    suffix = file_path.suffix.lower()
    content_type_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    media_type = content_type_map.get(suffix, "application/octet-stream")

    # 下载文件名：使用 合同编号.扩展名，便于用户识别
    download_filename = f"{contract.contract_number}{suffix}"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=download_filename,
    )


@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: int,
    contract_data: ContractUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新合同"""
    contract = ContractService.get_contract(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # 权限检查：income 可改任意合同，expense 不可修改
    if current_user.role == Role.EXPENSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权修改合同")

    updated_contract = ContractService.update_contract(db, contract_id, contract_data, updated_by=current_user.id)
    
    return updated_contract


@router.post("/{contract_id}/complete", response_model=ContractResponse)
def complete_contract(
    contract_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """管理员标记合同为已完成"""
    contract = ContractService.get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")
    if contract.status == 'completed':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="合同已是完成状态")

    contract.status = 'completed'
    db.commit()
    db.refresh(contract)
    return contract


@router.delete("/{contract_id}")
def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除合同"""
    contract = ContractService.get_contract(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # 权限检查：admin 可删除所有；income 可删除自己录入的合同
    if not can_delete_contract(current_user, contract):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此合同"
        )
    
    try:
        success = ContractService.delete_contract(db, contract_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    if success:
        return {"message": "删除成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除失败"
        )


@router.post("/{contract_id}/confirm-parsed-data", response_model=ContractResponse)
def confirm_parsed_data(
    contract_id: int,
    parsed_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """确认或修正AI解析结果"""
    contract = ContractService.get_contract(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # 权限检查：income 可操作任意合同，expense 不可操作
    if current_user.role == Role.EXPENSE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权操作合同")

    # 更新解析数据
    confidence = parsed_data.get('confidence', 0.9)
    updated_contract = ContractService.update_contract_data(
        db=db,
        contract_id=contract_id,
        contract_data=parsed_data.get('data', {}),
        confidence=confidence,
        updated_by=current_user.id,
    )
    
    return updated_contract



