"""
付款服务
"""
import logging
from decimal import Decimal
from datetime import date
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

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
        type: str = "income",
        payee_name: str = None,
    ) -> Payment:
        """
        创建付款记录并自动计算汇率，始终创建为 paid 状态。

        Args:
            type: income（收入）或 expense（支出）
            payee_name: 收款方名称（仅 expense 使用）
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
            type=type,
            currency=currency,
            amount=amount,
            paid_amount=amount,
            exchange_rate=exchange_rate,
            amount_in_cny=amount_in_cny,
            paid_amount_in_cny=amount_in_cny,
            paid_date=paid_date,
            payment_method=payment_method,
            payee_name=payee_name if type == "expense" else None,
            receipt_image_path=receipt_image_path,
            notes=notes,
            status='paid',
            created_by=created_by,
        )

        db.add(payment)

        # 按 type 分支更新合同汇总
        if type == "expense":
            PaymentService._add_to_contract_expense(db, contract, amount, currency, amount_in_cny, paid_date)
        else:
            PaymentService._add_to_contract_paid(db, contract, amount, currency, amount_in_cny, paid_date)

        db.commit()
        db.refresh(payment)

        return payment

    @staticmethod
    def get_next_installment_number(db: Session, contract_id: int, payment_type: str) -> int:
        """获取指定合同和类型的下一个期数编号"""
        max_num = db.query(func.max(Payment.installment_number)).filter(
            Payment.contract_id == contract_id,
            Payment.type == payment_type,
        ).scalar() or 0
        return max_num + 1

    @staticmethod
    def _add_to_contract_paid(
        db: Session, contract: Contract, amount: Decimal,
        currency: str, amount_in_cny: Decimal, paid_date: date
    ):
        """将一笔收入加入合同的已付金额"""
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

        # 收入达标自动完成合同
        if contract.paid_amount_in_cny and contract.total_amount_in_cny and contract.paid_amount_in_cny >= contract.total_amount_in_cny:
            contract.status = 'completed'

    @staticmethod
    def _add_to_contract_expense(
        db: Session, contract: Contract, amount: Decimal,
        currency: str, amount_in_cny: Decimal, paid_date: date
    ):
        """将一笔支出加入合同的支出汇总（不影响合同完成状态）"""
        contract.total_expense = (contract.total_expense or 0) + amount
        contract.total_expense_in_cny = (contract.total_expense_in_cny or 0) + amount_in_cny

    @staticmethod
    def _subtract_from_contract_expense(
        db: Session, contract: Contract, amount: Decimal, amount_in_cny: Decimal
    ):
        """删除支出时扣减合同支出汇总，保底为 0"""
        contract.total_expense = max((contract.total_expense or 0) - amount, 0)
        contract.total_expense_in_cny = max((contract.total_expense_in_cny or 0) - amount_in_cny, 0)

    @staticmethod
    def get_contract_payments(db: Session, contract_id: int, type_filter: str = None):
        """
        获取合同的付款记录，按收入/支出分组返回。

        Args:
            type_filter: 可选 "income" 或 "expense" 只返回对应类型
        """
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        query = db.query(Payment).filter(Payment.contract_id == contract_id)
        if type_filter:
            query = query.filter(Payment.type == type_filter)
        all_payments = query.order_by(Payment.installment_number).all()

        # 按类型分组
        income_payments = [p for p in all_payments if p.type == "income"]
        expense_payments = [p for p in all_payments if p.type == "expense"]

        total_paid_cny = sum(p.paid_amount_in_cny or 0 for p in income_payments)
        total_expense_cny = sum(p.paid_amount_in_cny or 0 for p in expense_payments)

        from app.schemas.payment import PaymentResponse
        income_data = [PaymentResponse.model_validate(p).model_dump() for p in income_payments]
        expense_data = [PaymentResponse.model_validate(p).model_dump() for p in expense_payments]

        return {
            "contract_id": contract_id,
            "contract_number": contract.contract_number,
            "income": {
                "payments": income_data,
                "total_amount": float(contract.total_amount),
                "paid_amount": float(contract.paid_amount),
                "remaining_amount": float(contract.remaining_amount or 0),
                "total_paid_in_cny": float(total_paid_cny),
            },
            "expense": {
                "payments": expense_data,
                "total_expense": float(contract.total_expense or 0),
                "total_expense_in_cny": float(contract.total_expense_in_cny or 0),
            },
            "profit_in_cny": float(total_paid_cny - total_expense_cny),
        }

    @staticmethod
    def delete_payment(db: Session, payment_id: int, user_id: int = None) -> bool:
        """硬删除付款记录，反写合同金额，清理凭证文件"""
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

        # 按 type 分支反写合同
        if contract and payment.status == 'paid' and payment.paid_amount:
            if payment.type == "expense":
                PaymentService._subtract_from_contract_expense(
                    db, contract, payment.paid_amount, payment.paid_amount_in_cny or 0
                )
            else:
                # 收入扣减
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
                    "type": payment.type,
                    "status": payment.status,
                    "deleted_file": deleted_file,
                },
            )

        logger.info("付款已删除: id=%d, contract_id=%d, type=%s", payment_id, payment.contract_id, payment.type)
        return True
