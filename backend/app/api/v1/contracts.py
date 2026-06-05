"""
合同管理API路由
"""
import logging
from typing import Optional, List
from decimal import Decimal
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import date

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.models.contract import Contract
from app.schemas.contract import (
    ContractCreate, ContractUpdate, ContractResponse, ContractParseResult,
    AnalyzeFileRequest, ContractCreateFromAnalysis, ResolveCustomerRequest,
)
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user, require_role
from app.models.user import User
from app.services.contract_service import ContractService
from app.utils.file_utils import save_uploaded_file, calculate_file_hash
from app.config import settings

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ContractResponse])
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同列表"""
    # admin/expense 可查看全部，income 只看自己负责的
    if current_user.role == "income":
        sales_person_id = current_user.id
    else:
        sales_person_id = None

    # 解析 customer_ids
    parsed_customer_ids: Optional[List[int]] = None
    if customer_ids:
        parsed_customer_ids = [int(cid.strip()) for cid in customer_ids.split(",") if cid.strip()]

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
        sales_person_id=sales_person_id
    )
    
    return PaginatedResponse(
        items=[ContractResponse.model_validate(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.post("/analyze-file")
def analyze_file(
    req: AnalyzeFileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分析已上传的合同文件（同步），返回 AI 提取的结构化数据 + 重复检测。"""
    if current_user.role not in ("admin", "income"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅 admin 或 income 角色可分析合同")

    from app.services.contract_analyzer import ContractAnalyzer

    file_path = ContractAnalyzer.resolve_file_path(req.file_id, current_user.id)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在，请重新上传")

    try:
        result = ContractAnalyzer.analyze_file(
            file_path, db, current_user.id,
            skip_duplicate_check=req.skip_duplicate_check,
        )
    except Exception as e:
        logger.exception("合同文件分析失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"分析失败: {str(e)}")

    return ResponseModel(code=200, data=result)


@router.post("/resolve-customer")
def resolve_customer(
    req: ResolveCustomerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从 AI 分析结果自动关联或创建客户。"""
    if current_user.role not in ("admin", "income"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅 admin 或 income 角色可操作")

    from app.services.customer_service import CustomerService

    party_info = req.analysis_data.get(req.party) or {}
    name = (party_info.get("name") or "").strip()
    phone = (party_info.get("phone") or "").strip() or None
    id_number = (party_info.get("id_number") or "").strip() or None

    if not name:
        return ResponseModel(code=200, data={
            "success": False,
            "error": "未识别到客户姓名",
            "party_info": party_info,
        })

    customer, created = CustomerService.create_or_get(
        db=db,
        name=name,
        phone=phone,
        id_card_number=id_number,
        created_by=current_user.id,
    )

    return ResponseModel(code=200, data={
        "success": True,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "created": created,
        },
        "party_info": party_info,
    })


@router.post("/create-from-analysis")
def create_from_analysis(
    req: ContractCreateFromAnalysis,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """根据 AI 分析结果（经用户确认/编辑后）创建合同 + 自动付款记录。"""
    if current_user.role not in ("admin", "income"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅 admin 或 income 角色可创建合同")

    from app.services.contract_analyzer import ContractAnalyzer, auto_create_payments_from_terms
    from app.models.customer import Customer

    # 验证客户存在
    customer = db.query(Customer).filter(
        Customer.id == req.customer_id, Customer.is_deleted == False
    ).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"客户不存在: {req.customer_id}")

    # 解析文件路径 + 移动到永久目录
    temp_path = ContractAnalyzer.resolve_file_path(req.file_id, current_user.id)
    file_hash = None
    original_file_path = f"agent_upload/{req.file_id}"

    if temp_path:
        with open(temp_path, "rb") as f:
            file_hash = calculate_file_hash(f.read())

        # 基于文件 hash 重复检测（soft warning：已在 analyze-file 阶段提醒用户，
        # 用户确认"仍然创建"后此处仅记录日志，不阻断）
        existing = db.query(Contract).filter(
            Contract.file_hash == file_hash,
            Contract.is_deleted == False,
        ).first()
        if existing:
            logger.warning(
                "重复文件创建: user=%d, file_hash=%s, existing_contract=%d/%s",
                current_user.id, file_hash[:8], existing.id, existing.contract_number,
            )

        contract_number = ContractService.generate_contract_number()
        original_file_path = ContractAnalyzer.copy_to_contract_dir(temp_path, contract_number)
    else:
        contract_number = ContractService.generate_contract_number()

    # 构建合同创建数据
    contract_create = ContractCreate(
        contract_number=contract_number,
        customer_id=req.customer_id,
        original_file_path=original_file_path,
        file_hash=file_hash,
        status="active",
        title=req.title,
        business_type=req.business_type,
        business_description=req.business_description,
        currency=req.currency,
        total_amount=req.total_amount,
        signed_date=req.signed_date,
        start_date=req.start_date,
        end_date=req.end_date,
        wechat_group=req.wechat_group,
        remarks=req.remarks,
    )

    try:
        contract = ContractService.create_contract(
            db=db,
            contract_data=contract_create,
            sales_person_id=current_user.id,
        )

        # 写入 contract_data JSON
        contract_data_json = dict(req.analysis_data) if req.analysis_data else {}
        contract_data_json["source"] = "wizard"
        contract_data_json["file_id"] = req.file_id
        # 覆盖 payment_terms 为用户确认后的版本
        if req.payment_terms:
            contract_data_json["payment_terms"] = [t.model_dump(exclude_none=True) for t in req.payment_terms]
        contract.contract_data = contract_data_json

        # 合同全文
        if req.full_text:
            contract.contract_text = req.full_text

        # 置信度 + needs_review
        if req.confidence is not None:
            contract.confidence = round(req.confidence, 4)
            contract.needs_review = req.confidence < 0.85

        db.commit()
        db.refresh(contract)

        # 自动创建已支付的付款记录
        payment_terms_data = contract_data_json if req.payment_terms else None
        auto_payments = []
        if payment_terms_data and req.payment_terms:
            auto_payments = auto_create_payments_from_terms(
                contract, contract_data_json, db, current_user.id
            )

        return ResponseModel(code=200, data={
            "contract": {
                "id": contract.id,
                "contract_number": contract.contract_number,
                "customer_name": customer.name,
                "customer_id": req.customer_id,
                "title": contract.title,
                "currency": contract.currency,
                "total_amount": float(contract.total_amount),
                "status": contract.status,
                "confidence": float(contract.confidence) if contract.confidence else None,
                "needs_review": contract.needs_review,
            },
            "auto_payments": auto_payments,
        })
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("从分析结果创建合同失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建合同失败: {str(e)}")


@router.post("/upload-and-parse", response_model=ContractParseResult, status_code=status.HTTP_202_ACCEPTED)
async def upload_and_parse_contract(
    file: UploadFile = File(...),
    customer_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传合同并启动AI解析"""
    # 仅 admin/income 可创建合同
    if current_user.role not in ("admin", "income"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅admin或income角色可创建合同")
    # 验证文件类型
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}"
        )

    # 验证文件大小
    content = await file.read()
    file_size = len(content)
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件过大，最大允许 {settings.MAX_FILE_SIZE // 1048576}MB"
        )
    await file.seek(0)  # 重置文件指针

    # 通过魔数字节验证文件真实类型
    from app.utils.file_utils import validate_file_magic
    if not validate_file_magic(content, ['jpeg', 'png', 'pdf']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容与声明的类型不匹配"
        )

    # 保存文件
    relative_path, file_hash, file_size = await save_uploaded_file(
        file=file,
        base_dir=settings.CONTRACT_UPLOAD_DIR,
        sub_dir=""
    )

    # 生成合同编号
    contract_number = ContractService.generate_contract_number()

    # 创建合同记录（草稿状态）
    contract_data = ContractCreate(
        contract_number=contract_number,
        title=file.filename,
        customer_id=customer_id,
        currency="CNY",
        total_amount=Decimal('0'),
        original_file_path=relative_path,
        file_hash=file_hash,
        signed_date=None
    )

    contract = ContractService.create_contract(
        db=db,
        contract_data=contract_data,
        sales_person_id=current_user.id
    )

    # 提交异步 Celery 任务进行 AI 解析
    try:
        from app.tasks.contract_tasks import parse_contract_task
        task = parse_contract_task.delay(contract.id, relative_path)
        task_id = task.id
    except Exception:
        # Celery 不可用则使用 mock（开发/测试环境）
        task_id = "mock-task-id"

    return ContractParseResult(
        task_id=task_id,
        status="parsing",
        contract_id=contract.id,
        message="合同上传成功，正在AI解析中..."
    )


@router.get("/parse-status/{contract_id}")
def get_parse_status(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询合同解析状态"""
    contract = ContractService.get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # 根据合同当前状态判断解析进度
    if contract.status == 'draft' and not contract.contract_data:
        return ResponseModel(code=200, data={
            "status": "processing",
            "progress": 50,
            "message": "正在调用AI解析合同内容..."
        })

    return ResponseModel(code=200, data={
        "status": "completed",
        "progress": 100,
        "contract_id": contract.id,
        "parsed_data": contract.contract_data,
        "confidence": float(contract.confidence) if contract.confidence else None
    })


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同详情"""
    contract = ContractService.get_contract(db, contract_id)

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
    
    # 权限检查：income 只能看自己合同，expense/admin 可看所有
    if current_user.role == "income" and contract.sales_person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此合同"
        )

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

    if current_user.role == "income" and contract.sales_person_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此合同")

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
    
    # 权限检查：income 只能改自己合同，expense 不可修改
    if current_user.role == "expense":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权修改合同")
    if current_user.role == "income" and contract.sales_person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此合同"
        )
    
    updated_contract = ContractService.update_contract(db, contract_id, contract_data)
    
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
    if current_user.role != "admin":
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
    
    # 权限检查：income 只能操作自己合同，expense 不可操作
    if current_user.role == "expense":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="expense角色无权操作合同")
    if current_user.role == "income" and contract.sales_person_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此合同"
        )
    
    # 更新解析数据
    confidence = parsed_data.get('confidence', 0.9)
    updated_contract = ContractService.update_contract_data(
        db=db,
        contract_id=contract_id,
        contract_data=parsed_data.get('data', {}),
        confidence=confidence
    )
    
    return updated_contract
