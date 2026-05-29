"""
付款服务
"""
import logging
from decimal import Decimal
from datetime import date
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.contract import Contract
from app.services.exchange_rate_service import ExchangeRateService
from app.services.audit_service import AuditService
from app.config import settings

logger = logging.getLogger(__name__)


class PaymentService:
    """付款服务类"""
    
    @staticmethod
    def create_payment_with_exchange_rate(
        db: Session,
        contract_id: int,
        installment_number: int,
        currency: str,
        amount: Decimal,
        paid_date: date,
        payment_method: str,
        receipt_image_path: str = None,
        notes: str = None,
        created_by: int = None,
        auto_confirm: bool = True
    ) -> Payment:
        """
        创建付款记录并自动计算汇率

        Args:
            auto_confirm: True 时立即确认为已付（有凭证），False 时标记为待凭证（pending_voucher）

        Returns:
            创建的付款记录
        """
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        exchange_rate, amount_in_cny = ExchangeRateService.convert_to_cny(
            db, amount, currency, paid_date
        )

        if auto_confirm:
            status = 'paid'
            paid_amount = amount
            paid_amount_in_cny = amount_in_cny
        else:
            status = 'pending_voucher'
            paid_amount = Decimal('0')
            paid_amount_in_cny = Decimal('0')

        payment = Payment(
            contract_id=contract_id,
            installment_number=installment_number,
            currency=currency,
            amount=amount,
            paid_amount=paid_amount,
            exchange_rate=exchange_rate,
            amount_in_cny=amount_in_cny,
            paid_amount_in_cny=paid_amount_in_cny,
            paid_date=paid_date,
            payment_method=payment_method,
            receipt_image_path=receipt_image_path,
            notes=notes,
            status=status,
            created_by=created_by
        )

        db.add(payment)

        if auto_confirm:
            PaymentService._add_to_contract_paid(db, contract, amount, currency, amount_in_cny, paid_date)

        db.commit()
        db.refresh(payment)

        return payment

    @staticmethod
    def confirm_payment(
        db: Session,
        payment_id: int,
        receipt_image_path: str = None
    ) -> Payment:
        """将待凭证付款确认为已付，更新合同已付金额"""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError(f"付款记录不存在：{payment_id}")
        if payment.status != 'pending_voucher':
            raise ValueError(f"当前状态为 {payment.status}，无法确认")

        contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
        if not contract:
            raise ValueError("关联合同不存在")

        payment.status = 'paid'
        payment.paid_amount = payment.amount
        payment.paid_amount_in_cny = payment.amount_in_cny

        if receipt_image_path:
            payment.receipt_image_path = receipt_image_path

        PaymentService._add_to_contract_paid(
            db, contract, payment.amount, payment.currency,
            payment.amount_in_cny, payment.paid_date
        )

        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def _add_to_contract_paid(
        db: Session, contract: Contract, amount: Decimal,
        currency: str, amount_in_cny: Decimal, paid_date: date
    ):
        """将一笔付款加入合同的已付金额"""
        if currency == contract.currency:
            contract.paid_amount += amount
        else:
            contract_rate, _ = ExchangeRateService.convert_to_cny(
                db, Decimal('1'), contract.currency, paid_date
            )
            if contract_rate:
                contract.paid_amount += (amount_in_cny / contract_rate).quantize(Decimal('0.01'))

        contract.paid_amount_in_cny = (contract.paid_amount_in_cny or 0) + amount_in_cny
        contract.remaining_amount = contract.total_amount - contract.paid_amount
        contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)

        if contract.paid_amount_in_cny and contract.total_amount_in_cny and contract.paid_amount_in_cny >= contract.total_amount_in_cny:
            contract.status = 'completed'
    
    @staticmethod
    def get_contract_payments(db: Session, contract_id: int):
        """获取合同的付款记录"""
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        payments = db.query(Payment).filter(
            Payment.contract_id == contract_id
        ).order_by(Payment.installment_number).all()

        total_paid = sum(p.paid_amount for p in payments)
        total_paid_cny = sum(p.paid_amount_in_cny or 0 for p in payments)

        from app.schemas.payment import PaymentResponse
        return {
            "contract_id": contract_id,
            "contract_number": contract.contract_number,
            "total_amount": contract.total_amount,
            "paid_amount": total_paid,
            "remaining_amount": contract.total_amount - total_paid,
            "total_amount_in_cny": contract.total_amount_in_cny,
            "paid_amount_in_cny": total_paid_cny,
            "remaining_amount_in_cny": contract.remaining_amount_in_cny,
            "payments": [PaymentResponse.model_validate(p).model_dump() for p in payments]
        }

    @staticmethod
    def delete_payment(db: Session, payment_id: int, user_id: int = None) -> bool:
        """硬删除付款记录，反写合同已付金额，清理凭证文件"""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return False

        contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()

        deleted_file = None
        if payment.receipt_image_path:
            receipt_path = Path(settings.RECEIPT_UPLOAD_DIR) / payment.receipt_image_path
            if receipt_path.exists():
                receipt_path.unlink()
                deleted_file = str(receipt_path)

        # 反写合同已付金额（仅已确认的付款才需要扣减）
        if contract and payment.status == 'paid' and payment.paid_amount:
            if payment.currency == contract.currency:
                contract.paid_amount -= payment.paid_amount
            contract.paid_amount_in_cny = (contract.paid_amount_in_cny or 0) - (payment.paid_amount_in_cny or 0)
            contract.remaining_amount = contract.total_amount - contract.paid_amount
            contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)
            if contract.status == 'completed' and contract.paid_amount_in_cny < contract.total_amount_in_cny:
                contract.status = 'active'

        db.delete(payment)
        db.commit()

        if user_id:
            AuditService.log(
                db,
                user_id=user_id,
                action="delete",
                entity_type="payment",
                entity_id=payment_id,
                old_values={
                    "contract_id": payment.contract_id,
                    "amount": float(payment.amount) if payment.amount else None,
                    "currency": payment.currency,
                    "status": payment.status,
                    "deleted_file": deleted_file,
                },
            )

        logger.info("付款已删除: id=%d, contract_id=%d", payment_id, payment.contract_id)
        return True
