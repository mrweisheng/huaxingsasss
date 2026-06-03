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
from app.schemas.payment import PaymentUpdate
from app.services.exchange_rate_service import ExchangeRateService
from app.services.audit_service import AuditService
from app.config import settings

logger = logging.getLogger(__name__)


class PaymentService:
    """付款服务类"""

    @staticmethod
    def _generate_description(contract, payment_type, installment_number, payee_name=None):
        """根据合同信息自动生成付款的可读描述"""
        parts = [
            contract.contract_number or "",
            getattr(contract.customer, 'name', None) or "未知客户",
            contract.business_description or "",
        ]
        prefix = " ".join(p for p in parts if p)
        if payment_type == "income":
            return f"{prefix} 第{installment_number}期收款"
        return f"{prefix} 第{installment_number}期支出→{payee_name or '未知'}"

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
        installment_name: str = None,
        receipt_data: dict = None,
    ) -> Payment:
        """
        创建付款记录并自动计算汇率。
        无凭证时 status='pending' 不参与结算，有凭证时 status='paid' 自动累加合同金额。

        Args:
            type: income（收入）或 expense（支出）
            payee_name: 收款方名称（仅 expense 使用）
        """
        if type not in ("income", "expense"):
            raise ValueError(f"无效的付款类型: {type}，必须是 income 或 expense")

        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        # 以合同货币为基准：同币种不换算，混币种按实时汇率换算
        # 同币种非 CNY（如港币合同付港币）：仍计算 CNY 等值，用于全局统计和利润计算
        if currency == "CNY" and contract.currency == "CNY":
            # 都是人民币，无需任何换算
            exchange_rate = None
            amount_in_cny = None
        elif currency != contract.currency:
            # 混币种：付款币种 ≠ 合同币种，按付款日汇率折算 CNY
            exchange_rate, amount_in_cny = ExchangeRateService.convert_to_cny(
                db, amount, currency, paid_date
            )
            logger.info(
                "混币种付款: payment=%s %s, contract=%s %s, rate=%s, amount_in_cny=%s CNY",
                amount, currency, contract.total_amount, contract.currency,
                exchange_rate, amount_in_cny,
            )
        else:
            # 同币种且非 CNY（如港币合同付港币）：计算 CNY 等值
            exchange_rate, amount_in_cny = ExchangeRateService.convert_to_cny(
                db, amount, currency, paid_date
            )
            logger.info(
                "同币种非CNY付款: payment=%s %s, rate=%s, amount_in_cny=%s CNY",
                amount, currency, exchange_rate, amount_in_cny,
            )

        has_receipt = bool(receipt_image_path)

        logger.info(
            "创建付款: contract_id=%d, type=%s, amount=%s %s, receipt=%s → status=%s",
            contract_id, type, amount, currency,
            receipt_image_path or "无",
            'paid' if has_receipt else 'pending',
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
            installment_name=installment_name,
            receipt_image_path=receipt_image_path,
            receipt_data=receipt_data,
            notes=notes,
            status='paid' if has_receipt else 'pending',
            created_by=created_by,
        )

        # 自动生成可读描述
        payment.description = PaymentService._generate_description(
            contract, type, installment_number, payee_name
        )

        db.add(payment)

        # 有凭证才参与结算：累加合同金额
        if has_receipt:
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
        """将一笔收入加入合同的已付金额。amount_in_cny 为 None 时跳过 CNY 字段更新。"""
        if currency == contract.currency:
            contract.paid_amount += amount
        else:
            contract_rate, _ = ExchangeRateService.convert_to_cny(
                db, Decimal('1'), contract.currency, paid_date
            )
            if contract_rate:
                contract.paid_amount += (amount_in_cny / contract_rate).quantize(Decimal('0.01'))

        # 仅当 amount_in_cny 存在时才更新 CNY 汇总字段（混币种才有）
        if amount_in_cny is not None:
            contract.paid_amount_in_cny = (contract.paid_amount_in_cny or 0) + amount_in_cny
            contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)

        contract.remaining_amount = contract.total_amount - contract.paid_amount

        # 统一用原币判断合同完成状态（paid_amount 始终为合同货币）
        if contract.paid_amount >= contract.total_amount:
            contract.status = 'completed'

    @staticmethod
    def _add_to_contract_expense(
        db: Session, contract: Contract, amount: Decimal,
        currency: str, amount_in_cny: Decimal, paid_date: date
    ):
        """将一笔支出加入合同的支出汇总（不影响合同完成状态）。amount_in_cny 为 None 时跳过 CNY 字段更新。"""
        if currency == contract.currency:
            contract.total_expense = (contract.total_expense or 0) + amount
        else:
            contract_rate, _ = ExchangeRateService.convert_to_cny(
                db, Decimal('1'), contract.currency, paid_date
            )
            if contract_rate:
                contract.total_expense = (contract.total_expense or 0) + (amount_in_cny / contract_rate).quantize(Decimal('0.01'))
            else:
                contract.total_expense = (contract.total_expense or 0) + amount_in_cny

        # 仅当 amount_in_cny 存在时才更新 CNY 汇总字段
        if amount_in_cny is not None:
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

        total_paid_cny = sum(p.paid_amount_in_cny or 0 for p in income_payments if p.status == 'paid')
        total_expense_cny = sum(p.paid_amount_in_cny or 0 for p in expense_payments if p.status == 'paid')

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
    def update_payment(db: Session, payment_id: int, payment_data: PaymentUpdate) -> Optional[Payment]:
        """更新付款记录。补充凭证时自动从 pending 转为 paid 并参与结算。"""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return None

        was_pending = payment.status == 'pending'
        had_receipt = bool(payment.receipt_image_path) or bool(payment.receipt_data)

        update_data = payment_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(payment, field, value)

        # 补充凭证时：pending → paid，累加合同金额参与结算
        # receipt_data（OCR 凭证数据）与 receipt_image_path（图片文件路径）都是凭证证据。
        # AI 分析收据后可能只传了 receipt_data 而没传 receipt_image_path（temp 文件已清理），
        # 此时仅凭 receipt_data 即可触发状态转换。
        now_has_receipt = bool(payment.receipt_image_path) or bool(payment.receipt_data)
        should_settle = False
        if was_pending and not had_receipt and now_has_receipt:
            should_settle = True
        elif payment.status == 'pending' and now_has_receipt:
            # 兜底：历史遗留——之前更新时 receipt_data 已写入但 status 未转换
            logger.warning(
                "payment stuck fix: payment_id=%d receipt_data/ receipt_image_path exists but status still pending",
                payment_id,
            )
            should_settle = True

        if should_settle:
            logger.info(
                "补充凭证触发结算: payment_id=%d, contract_id=%d, type=%s, amount=%s, status pending→paid",
                payment_id, payment.contract_id, payment.type, payment.paid_amount,
            )
            payment.status = 'paid'
            contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
            if contract:
                amount_in_cny = payment.paid_amount_in_cny  # 仅 CNY 合同+CNY 付款时为 None，_add_to_* 会跳过 CNY 更新
                if payment.type == "expense":
                    PaymentService._add_to_contract_expense(
                        db, contract, payment.paid_amount, payment.currency,
                        amount_in_cny, payment.paid_date
                    )
                else:
                    PaymentService._add_to_contract_paid(
                        db, contract, payment.paid_amount, payment.currency,
                        amount_in_cny, payment.paid_date
                    )

        db.commit()
        db.refresh(payment)
        return payment

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
                # 收入扣减：必须按币种/汇率折算扣减 paid_amount，避免跨币种时 paid_amount 与 paid_amount_in_cny 失同步
                contract.paid_amount_in_cny = (contract.paid_amount_in_cny or 0) - (payment.paid_amount_in_cny or 0)
                if payment.currency == contract.currency:
                    contract.paid_amount = (contract.paid_amount or 0) - (payment.paid_amount or 0)
                else:
                    # 跨币种：用付款日汇率反算回合同币种
                    if payment.paid_date and payment.paid_amount_in_cny and payment.paid_amount:
                        contract_rate, _ = ExchangeRateService.convert_to_cny(
                            db, Decimal('1'), contract.currency, payment.paid_date
                        )
                        if contract_rate:
                            contract.paid_amount = (contract.paid_amount or 0) - \
                                (payment.paid_amount_in_cny / contract_rate).quantize(Decimal('0.01'))
                # 保底为 0，避免历史脏数据导致负数
                contract.paid_amount = max(contract.paid_amount or 0, Decimal('0'))
                contract.paid_amount_in_cny = max(contract.paid_amount_in_cny or 0, Decimal('0'))
                contract.remaining_amount = (contract.total_amount or 0) - (contract.paid_amount or 0)
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
