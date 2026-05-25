"""
付款服务
"""
from decimal import Decimal
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.contract import Contract
from app.services.exchange_rate_service import ExchangeRateService


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
        created_by: int = None
    ) -> Payment:
        """
        创建付款记录并自动计算汇率

        Returns:
            创建的付款记录
        """
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        exchange_rate, amount_in_cny = ExchangeRateService.convert_to_cny(
            db, amount, currency, paid_date
        )

        payment = Payment(
            contract_id=contract_id,
            installment_number=installment_number,
            currency=currency,
            amount=amount,
            paid_amount=amount,
            exchange_rate=exchange_rate,
            amount_in_cny=amount_in_cny,
            paid_amount_in_cny=amount_in_cny,
            paid_date=paid_date,
            payment_method=payment_method,
            receipt_image_path=receipt_image_path,
            notes=notes,
            status='paid',
            created_by=created_by
        )

        db.add(payment)

        if currency == contract.currency:
            # 同币种直接累加原始币种口径
            contract.paid_amount += amount
        else:
            # 不同币种：将付款折算为合同币种后累加
            contract_rate, _ = ExchangeRateService.convert_to_cny(
                db, Decimal('1'), contract.currency, paid_date
            )
            if contract_rate:
                contract.paid_amount += (amount_in_cny / contract_rate).quantize(Decimal('0.01'))

        contract.paid_amount_in_cny = (contract.paid_amount_in_cny or 0) + amount_in_cny

        if contract.paid_amount_in_cny and contract.total_amount_in_cny and contract.paid_amount_in_cny >= contract.total_amount_in_cny:
            contract.status = 'completed'

        db.commit()
        db.refresh(payment)

        return payment
    
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
        
        return {
            "contract_id": contract_id,
            "contract_number": contract.contract_number,
            "total_amount": contract.total_amount,
            "paid_amount": total_paid,
            "remaining_amount": contract.total_amount - total_paid,
            "total_amount_in_cny": contract.total_amount_in_cny,
            "paid_amount_in_cny": total_paid_cny,
            "remaining_amount_in_cny": contract.remaining_amount_in_cny,
            "payments": payments
        }
