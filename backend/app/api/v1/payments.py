"""
付款管理API路由
"""
import logging
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import date

from app.db.session import get_db
from app.schemas.payment import PaymentResponse
from app.schemas.response import ResponseModel, PaginatedResponse, PaginationModel
from app.api.dependencies import get_current_user
from app.core.permissions import Role, is_admin
from app.models.user import User
from app.models.payment import Payment
from app.models.contract import Contract
from app.models.customer import Customer
from app.services.payment_service import PaymentService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[PaymentResponse])
def list_payments(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    contract_id: Optional[int] = Query(None, description="合同ID"),
    keyword: Optional[str] = Query(None, description="搜索关键词（合同编号/客户名称）"),
    status: Optional[str] = Query(None, description="付款状态"),
    payment_type: Optional[str] = Query(None, alias="type", description="类型: income/expense"),
    date_from: Optional[date] = Query(None, description="付款日期起"),
    date_to: Optional[date] = Query(None, description="付款日期止"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取付款记录列表"""
    query = db.query(Payment).filter(Payment.is_deleted == False)\
        .outerjoin(Contract, Payment.contract_id == Contract.id)\
        .outerjoin(Customer, Contract.customer_id == Customer.id)

    if contract_id:
        query = query.filter(Payment.contract_id == contract_id)
    if keyword:
        query = query.filter(
            Contract.contract_number.ilike(f'%{keyword}%') |
            Customer.name.ilike(f'%{keyword}%')
        )
    if status:
        query = query.filter(Payment.status == status)
    if payment_type:
        query = query.filter(Payment.type == payment_type)
    if date_from:
        query = query.filter(Payment.paid_date >= date_from)
    if date_to:
        query = query.filter(Payment.paid_date <= date_to)

    # 角色权限：income 只看收入+自己合同，expense 只看支出+自己创建的，admin 全量
    if current_user.role == Role.INCOME:
        query = query.filter(Payment.type == "income")
        query = query.filter(Contract.sales_person_id == current_user.id)
    elif current_user.role == Role.EXPENSE:
        query = query.filter(Payment.type == "expense")
        query = query.filter(Payment.created_by == current_user.id)

    total = query.count()
    items = query.order_by(Payment.paid_date.desc().nullsfirst(), Payment.created_at.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()

    # 填充 contract_number、customer_name、contract_business_description
    for item in items:
        contract = db.query(Contract).filter(Contract.id == item.contract_id).first()
        if contract:
            item.contract_number = contract.contract_number
            item.contract_business_description = contract.business_description
            if contract.customer_id:
                customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
                item.customer_name = customer.name if customer else None

    return PaginatedResponse(
        items=[PaymentResponse.model_validate(item) for item in items],
        pagination=PaginationModel(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page
        )
    )


@router.get("/contract/{contract_id}")
def get_contract_payments(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同的付款记录（按角色过滤类型）"""
    # P1-3: 校验合同存在 + income 角色归属
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    if current_user.role == Role.INCOME:
        type_filter = "income"
        if contract.sales_person_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此合同")
    elif current_user.role == Role.EXPENSE:
        type_filter = "expense"
    else:
        type_filter = None

    result = PaymentService.get_contract_payments(db, contract_id, type_filter=type_filter)

    return ResponseModel(
        code=200,
        message="success",
        data=result
    )


@router.get("/{payment_id}/receipt")
def get_receipt_image(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查看付款凭证图片"""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="付款记录不存在")

    # 权限检查：admin 全量，income 只看自己合同，expense 只看自己创建的
    contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
    if current_user.role == Role.INCOME and contract and contract.sales_person_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    if current_user.role == Role.EXPENSE and payment.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")

    if not payment.receipt_image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证文件不存在")

    file_path = Path(settings.RECEIPT_UPLOAD_DIR) / payment.receipt_image_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证文件已丢失")

    media_type = "application/octet-stream"
    suffix = file_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif suffix == ".png":
        media_type = "image/png"

    return FileResponse(path=str(file_path), media_type=media_type)


@router.delete("/{payment_id}")
def delete_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除付款记录"""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可删除付款记录"
        )

    success = PaymentService.delete_payment(db, payment_id, user_id=current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="付款记录不存在"
        )

    return {"message": "删除成功"}
