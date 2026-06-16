"""
收款账户管理 API 路由

挂载在 /api/v1/payment-accounts 前缀下：
  GET    /                    列出收款账户（所有角色可见）
  POST   /                    新增收款账户（仅 admin）
  PUT    /{account_id}        更新收款账户（仅 admin）
  DELETE /{account_id}        删除收款账户（仅 admin）
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.payment_account import (
    PaymentAccountCreate,
    PaymentAccountUpdate,
    PaymentAccountResponse,
)
from app.services.payment_account_service import PaymentAccountService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[PaymentAccountResponse])
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出所有收款账户（所有角色可见）"""
    return PaymentAccountService.list_accounts(db)


@router.post("", response_model=PaymentAccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    data: PaymentAccountCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """新增收款账户（仅 admin）"""
    return PaymentAccountService.create_account(db, data, user_id=current_user.id)


@router.put("/{account_id}", response_model=PaymentAccountResponse)
def update_account(
    account_id: int = Path(..., ge=1),
    data: PaymentAccountUpdate = ...,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """更新收款账户（仅 admin）"""
    account = PaymentAccountService.update_account(db, account_id, data)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账户不存在")
    return account


@router.delete("/{account_id}")
def delete_account(
    account_id: int = Path(..., ge=1),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """删除收款账户（仅 admin）"""
    success = PaymentAccountService.delete_account(db, account_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账户不存在")
    return {"message": "删除成功"}
