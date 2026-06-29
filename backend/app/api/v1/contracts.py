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
)
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user, require_role
from app.core.permissions import Role, is_admin
from app.models.user import User
from app.services.contract_service import ContractService
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
    
    # 权限检查（仅管理员可删除）
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可删除合同"
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



