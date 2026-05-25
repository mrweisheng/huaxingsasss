"""
付款管理API路由
"""
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from datetime import date

from app.db.session import get_db
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse, PaymentPlanCreate
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.payment import Payment
from app.models.contract import Contract
from app.models.customer import Customer
from app.services.payment_service import PaymentService
from app.utils.file_utils import save_uploaded_file
from app.config import settings

router = APIRouter()


@router.get("", response_model=PaginatedResponse[PaymentResponse])
def list_payments(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    contract_id: Optional[int] = Query(None, description="合同ID"),
    status: Optional[str] = Query(None, description="付款状态"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取付款记录列表"""
    query = db.query(Payment).outerjoin(Contract, Payment.contract_id == Contract.id)\
        .outerjoin(Customer, Contract.customer_id == Customer.id)

    if contract_id:
        query = query.filter(Payment.contract_id == contract_id)
    if status:
        query = query.filter(Payment.status == status)

    # 非管理员/财务只能看自己合同的付款
    if current_user.role not in ("admin", "finance"):
        query = query.filter(Contract.sales_person_id == current_user.id)

    total = query.count()
    items = query.order_by(Payment.paid_date.desc().nullsfirst(), Payment.created_at.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()

    # 填充 contract_number 和 customer_name
    for item in items:
        contract = db.query(Contract).filter(Contract.id == item.contract_id).first()
        if contract:
            item.contract_number = contract.contract_number
            if contract.customer_id:
                customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
                item.customer_name = customer.name if customer else None

    return PaginatedResponse(
        items=[PaymentResponse.from_orm(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.post("/upload-receipt", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    contract_id: int = Form(...),
    installment_number: int = Form(...),
    currency: str = Form("CNY"),
    paid_amount: Decimal = Form(...),
    paid_date: date = Form(...),
    payment_method: str = Form(...),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传付款凭证并登记"""
    receipt_path = None

    if file:
        # 验证文件大小
        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大允许 {settings.MAX_FILE_SIZE // 1048576}MB"
            )
        await file.seek(0)

        relative_path, file_hash, file_size = await save_uploaded_file(
            file=file,
            base_dir=settings.RECEIPT_UPLOAD_DIR,
            sub_dir=""
        )
        receipt_path = relative_path
    
    payment = PaymentService.create_payment_with_exchange_rate(
        db=db,
        contract_id=contract_id,
        installment_number=installment_number,
        currency=currency,
        amount=paid_amount,
        paid_date=paid_date,
        payment_method=payment_method,
        receipt_image_path=receipt_path,
        notes=notes,
        created_by=current_user.id
    )
    
    return payment


@router.get("/contract/{contract_id}")
def get_contract_payments(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同的付款记录"""
    result = PaymentService.get_contract_payments(db, contract_id)
    
    return ResponseModel(
        code=200,
        message="success",
        data=result
    )
