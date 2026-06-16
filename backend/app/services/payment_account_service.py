"""
收款账户服务层
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.payment_account import PaymentAccount
from app.schemas.payment_account import PaymentAccountCreate

logger = logging.getLogger(__name__)


class PaymentAccountService:
    """收款账户服务"""
    
    @staticmethod
    def list_accounts(db: Session) -> List[PaymentAccount]:
        """列出所有有效收款账户"""
        return (
            db.query(PaymentAccount)
            .filter(PaymentAccount.is_deleted == False)
            .order_by(PaymentAccount.sort_order.asc(), PaymentAccount.id.asc())
            .all()
        )
    
    @staticmethod
    def create_account(db: Session, data: PaymentAccountCreate, user_id: int) -> PaymentAccount:
        """创建收款账户"""
        if data.is_default:
            db.query(PaymentAccount).filter(
                PaymentAccount.is_default == True,
                PaymentAccount.is_deleted == False,
            ).update({"is_default": False})
        
        account = PaymentAccount(
            account_type=data.account_type,
            title=data.title,
            account_name=data.account_name,
            account_number=data.account_number,
            qr_code_url=data.qr_code_url,
            fps_id=data.fps_id,
            bank_name=data.bank_name,
            branch=data.branch,
            address=data.address,
            phone=data.phone,
            swift_code=data.swift_code,
            extra_info=data.extra_info or {},
            is_default=data.is_default,
            sort_order=data.sort_order,
            created_by=user_id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account
    
    @staticmethod
    def delete_account(db: Session, account_id: int) -> bool:
        """软删收款账户"""
        account = (
            db.query(PaymentAccount)
            .filter(PaymentAccount.id == account_id, PaymentAccount.is_deleted == False)
            .first()
        )
        if not account:
            return False
        account.soft_delete()
        db.commit()
        return True
