"""
收款账户服务层
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.payment_account import PaymentAccount
from app.schemas.payment_account import PaymentAccountCreate, PaymentAccountUpdate

logger = logging.getLogger(__name__)


class PaymentAccountService:
    """收款账户服务"""
    
    @staticmethod
    def list_accounts(db: Session) -> List[PaymentAccount]:
        """列出所有有效收款账户（按 sort_order 升序）"""
        return (
            db.query(PaymentAccount)
            .filter(PaymentAccount.is_deleted == False)
            .order_by(PaymentAccount.sort_order.asc(), PaymentAccount.id.asc())
            .all()
        )
    
    @staticmethod
    def get_account(db: Session, account_id: int) -> Optional[PaymentAccount]:
        """获取单个收款账户"""
        return (
            db.query(PaymentAccount)
            .filter(
                PaymentAccount.id == account_id,
                PaymentAccount.is_deleted == False,
            )
            .first()
        )
    
    @staticmethod
    def create_account(
        db: Session,
        data: PaymentAccountCreate,
        user_id: int,
    ) -> PaymentAccount:
        """创建收款账户"""
        # 如果设置为默认，先取消其他默认
        if data.is_default:
            db.query(PaymentAccount).filter(
                PaymentAccount.is_default == True,
                PaymentAccount.is_deleted == False,
            ).update({"is_default": False})
        
        account = PaymentAccount(
            name=data.name,
            account_type=data.account_type,
            bank_name=data.bank_name,
            account_name=data.account_name,
            account_number=data.account_number,
            branch=data.branch,
            address=data.address,
            phone=data.phone,
            swift_code=data.swift_code,
            fps_id=data.fps_id,
            qr_code_url=data.qr_code_url,
            is_default=data.is_default,
            sort_order=data.sort_order,
            remarks=data.remarks,
            created_by=user_id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        
        logger.info("收款账户已创建: id=%s, name=%s", account.id, account.name)
        return account
    
    @staticmethod
    def update_account(
        db: Session,
        account_id: int,
        data: PaymentAccountUpdate,
    ) -> Optional[PaymentAccount]:
        """更新收款账户"""
        account = PaymentAccountService.get_account(db, account_id)
        if not account:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        # 如果设置为默认，先取消其他默认
        if update_data.get("is_default"):
            db.query(PaymentAccount).filter(
                PaymentAccount.is_default == True,
                PaymentAccount.is_deleted == False,
                PaymentAccount.id != account_id,
            ).update({"is_default": False})
        
        for field, value in update_data.items():
            setattr(account, field, value)
        
        db.commit()
        db.refresh(account)
        
        logger.info("收款账户已更新: id=%s, name=%s", account.id, account.name)
        return account
    
    @staticmethod
    def delete_account(db: Session, account_id: int) -> bool:
        """软删收款账户"""
        account = PaymentAccountService.get_account(db, account_id)
        if not account:
            return False
        
        account.soft_delete()
        db.commit()
        
        logger.info("收款账户已删除: id=%s, name=%s", account.id, account.name)
        return True
