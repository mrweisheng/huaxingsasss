"""
付款服务
"""
import logging
from decimal import Decimal
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, contains_eager
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.models.payment import Payment
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.payment_account import PaymentAccount
from app.models.audit_log import AuditLog
from app.models.payment_override_audit import PaymentOverrideAudit
from app.schemas.payment import PaymentUpdate
from app.services.exchange_rate_service import ExchangeRateService
from app.services.audit_service import AuditService
from app.config import settings

logger = logging.getLogger(__name__)


class PaymentService:
    """付款服务类"""

    # ── 付款方式归一化（payment_method 合法值：bank_transfer/wechat/alipay/cash/check）──
    # account_type（PaymentAccount）→ payment_method：bank 与 bank_transfer 命名不同，需归一
    _ACCOUNT_TYPE_TO_METHOD = {
        "bank": "bank_transfer",
        "alipay": "alipay",
        "wechat": "wechat",
        "cash": "cash",
    }

    @staticmethod
    def _method_from_account_type(account_type: Optional[str]) -> Optional[str]:
        """收款账户类型 → 付款方式。other/None/未知类型返回 None（交 AI 凭证检测补全）。"""
        if not account_type:
            return None
        return PaymentService._ACCOUNT_TYPE_TO_METHOD.get(account_type)

    @staticmethod
    def _method_from_document_type(doc_type: Optional[str]) -> Optional[str]:
        """VL 凭证类型（document_type）→ 付款方式。
        prompt 返回值见 ai/prompts.py RECEIPT_ANALYSIS_PROMPT：
        bank_transfer/wechat/alipay/check 原样；cash_receipt→cash；其它→None。"""
        if not doc_type:
            return None
        if doc_type == "cash_receipt":
            return "cash"
        if doc_type in ("bank_transfer", "wechat", "alipay", "cash", "check"):
            return doc_type
        return None

    @staticmethod
    def get_payments(
        db: Session,
        page: int = 1,
        per_page: int = 20,
        contract_id: Optional[int] = None,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        payment_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        role_type_filter: Optional[str] = None,
    ) -> Tuple[List[Payment], int]:
        """
        获取付款记录列表（带 contract / customer 一次性 join 加载，消除 N+1）。

        Args:
            role_type_filter: 角色级类型过滤。'income' / 'expense' / None（admin 全量）。
                与显式 payment_type 是 AND 关系。

        Returns:
            (付款列表, 总数)。每条 Payment 已挂上 contract_number / customer_name /
            contract_business_description / contract_wechat_group 临时字段供 PaymentResponse 序列化。
        """
        query = (
            db.query(Payment)
            .outerjoin(Contract, Payment.contract_id == Contract.id)
            .outerjoin(Customer, Contract.customer_id == Customer.id)
            .options(
                contains_eager(Payment.contract).contains_eager(Contract.customer)
            )
            .filter(Payment.is_deleted == False)
        )

        if contract_id:
            query = query.filter(Payment.contract_id == contract_id)
        if keyword:
            query = query.filter(
                or_(
                    Contract.contract_number.ilike(f"%{keyword}%"),
                    Customer.name.ilike(f"%{keyword}%"),
                )
            )
        if status:
            query = query.filter(Payment.status == status)
        if payment_type:
            query = query.filter(Payment.type == payment_type)
        if role_type_filter in ("income", "expense"):
            query = query.filter(Payment.type == role_type_filter)
        if date_from:
            query = query.filter(Payment.paid_date >= date_from)
        if date_to:
            query = query.filter(Payment.paid_date <= date_to)

        total = query.count()
        # 排序：凭证校验不符(failed)优先置顶醒目，其次按付款日期倒序
        items = (
            query.order_by(
                # failed 排前：CASE 当 verification_status='failed' 返回 0，否则 1
                func.coalesce(Payment.verification_status != 'failed', True),
                Payment.paid_date.desc().nullsfirst(),
                Payment.created_at.desc(),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        # 把 join 出来的字段挂到 ORM 对象上，PaymentResponse 直接读
        for item in items:
            ct = item.contract
            if ct:
                item.contract_number = ct.contract_number
                item.contract_business_description = ct.business_description
                item.contract_wechat_group = ct.wechat_group
                item.contract_currency = ct.currency
                item.customer_name = ct.customer.name if ct.customer else None
            else:
                item.contract_number = None
                item.contract_business_description = None
                item.contract_wechat_group = None
                item.contract_currency = None
                item.customer_name = None

        # 批量填充 payment_account_title（避免 relationship 懒加载的 N+1）
        account_ids = {item.payment_account_id for item in items if item.payment_account_id}
        account_title_map = {}
        if account_ids:
            from app.models.payment_account import PaymentAccount
            accts = db.query(PaymentAccount).filter(PaymentAccount.id.in_(account_ids)).all()
            account_title_map = {a.id: a.title for a in accts}
        for item in items:
            item.payment_account_title = account_title_map.get(item.payment_account_id) if item.payment_account_id else None

        return items, total

    @staticmethod
    def _generate_description(contract, payment_type, installment_number, payee_name=None, installment_name=None):
        """生成付款说明：优先用期数名称（如"定金"、"保险费用"），否则用合同业务描述兜底"""
        if installment_name:
            return installment_name
        biz = contract.business_description or ""
        if biz:
            return biz
        if payment_type == "income":
            return f"第{installment_number}期收款"
        return f"第{installment_number}期支出→{payee_name or '未知'}"

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
        receipt_file_hash: str = None,
        description: str = None,
        require_verification: bool = False,
    ) -> Payment:
        """
        创建付款记录并自动计算汇率。
        无凭证时 status='pending' 不参与结算，有凭证时 status='paid' 自动累加合同金额。

        Args:
            type: income（收入）或 expense（支出）
            payee_name: 收款方名称（仅 expense 使用）
            require_verification: 表单入口专用——收入凭证需异步校验，即使有凭证也先落 pending 不结算，
                校验通过后由 Celery task 回填 paid。不影响 agent 旧路径（默认 False，有凭证直接 paid）。
        """
        if type not in ("income", "expense"):
            raise ValueError(f"无效的付款类型: {type}，必须是 income 或 expense")

        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        if currency == "CNY" and contract.currency == "CNY":
            # 纯人民币：汇率 1:1，CNY 等值即原值（统一 _in_cny 字段，方便上层汇总）
            exchange_rate = Decimal('1.0')
            amount_in_cny = amount
        else:
            # 非纯 CNY：计算 CNY 等值（同币种用于全局统计，混币种还用于折算）
            exchange_rate, amount_in_cny = ExchangeRateService.convert_to_cny(
                db, amount, currency, paid_date
            )
            logger.info(
                "付款 CNY 等值: %s %s → %s CNY, rate=%s",
                amount, currency, amount_in_cny, exchange_rate,
            )

        has_receipt = bool(receipt_image_path)
        # require_verification=True：有凭证也先 pending，等异步校验通过再结算（表单收入入口，开关开启时）
        # require_verification=False（支出 / 现阶段无凭证收入）：直接 paid 结算，与有无凭证无关
        will_settle = not require_verification

        logger.info(
            "创建付款: contract_id=%d, type=%s, amount=%s %s, receipt=%s, require_verification=%s → status=%s",
            contract_id, type, amount, currency,
            receipt_image_path or "无",
            require_verification,
            'paid' if will_settle else 'pending',
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
            receipt_file_hash=receipt_file_hash,
            receipt_data=receipt_data,
            notes=notes,
            status='paid' if will_settle else 'pending',
            created_by=created_by,
        )

        # 生成可读描述：优先使用自定义描述，否则用期数名称或合同业务描述兜底
        payment.description = description or PaymentService._generate_description(
            contract, type, installment_number, payee_name, installment_name
        )

        db.add(payment)

        # 有凭证且非待校验才参与结算：累加合同金额
        if will_settle:
            if type == "expense":
                PaymentService._add_to_contract_expense(db, contract, amount, currency, amount_in_cny, paid_date)
            else:
                PaymentService._add_to_contract_paid(db, contract, amount, currency, amount_in_cny, paid_date)

        db.commit()
        db.refresh(payment)

        # 审计日志
        if created_by:
            try:
                AuditService.log(
                    db,
                    user_id=created_by,
                    action="create",
                    entity_type="payment",
                    entity_id=payment.id,
                    new_values={
                        "contract_id": contract_id,
                        "type": type,
                        "amount": float(amount) if amount else None,
                        "currency": currency,
                        "status": payment.status,
                        "installment_number": installment_number,
                        "paid_date": str(paid_date) if paid_date else None,
                    },
                )
            except Exception as e:
                logger.warning("审计日志写入失败: entity=payment, action=create, error=%s", e)

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
        """将一笔收入加入合同的已付金额。amount_in_cny 始终有值（CNY 合同为原值，非 CNY 合同为折算值）。"""
        if currency == contract.currency:
            contract.paid_amount += amount
        else:
            # 混币种：直接折算成合同币种
            _, converted = ExchangeRateService.convert_currency(
                db, amount, currency, contract.currency, paid_date
            )
            contract.paid_amount += converted

        # 统一更新 CNY 汇总字段（所有合同均维护 _in_cny，方便跨币种统计）
        contract.paid_amount_in_cny = (contract.paid_amount_in_cny or 0) + amount_in_cny
        contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)

        contract.remaining_amount = contract.total_amount - contract.paid_amount

    @staticmethod
    def _add_to_contract_expense(
        db: Session, contract: Contract, amount: Decimal,
        currency: str, amount_in_cny: Decimal, paid_date: date
    ):
        """将一笔支出加入合同的支出汇总（不影响合同完成状态）。amount_in_cny 始终有值。"""
        if currency == contract.currency:
            contract.total_expense = (contract.total_expense or 0) + amount
        else:
            # 混币种：直接折算成合同币种
            _, converted = ExchangeRateService.convert_currency(
                db, amount, currency, contract.currency, paid_date
            )
            contract.total_expense = (contract.total_expense or 0) + converted

        # 统一更新 CNY 汇总字段
        contract.total_expense_in_cny = (contract.total_expense_in_cny or 0) + amount_in_cny

    @staticmethod
    def _subtract_from_contract_expense(
        db: Session, contract: Contract, amount: Decimal,
        currency: str, amount_in_cny: Decimal, paid_date: date
    ):
        """删除支出时扣减合同支出汇总，保底为 0"""
        if currency == contract.currency:
            contract.total_expense = max((contract.total_expense or 0) - amount, 0)
        else:
            _, converted = ExchangeRateService.convert_currency(
                db, amount, currency, contract.currency, paid_date
            )
            contract.total_expense = max((contract.total_expense or 0) - converted, 0)
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

        # CNY 合同的 _in_cny 字段全为 None，直接用原值（原值即 CNY）
        if contract.currency == "CNY":
            total_paid_cny = sum(p.paid_amount or 0 for p in income_payments if p.status == 'paid')
            total_expense_cny = sum(p.paid_amount or 0 for p in expense_payments if p.status == 'paid')
        else:
            total_paid_cny = sum(p.paid_amount_in_cny or 0 for p in income_payments if p.status == 'paid')
            total_expense_cny = sum(p.paid_amount_in_cny or 0 for p in expense_payments if p.status == 'paid')

        from app.schemas.payment import PaymentResponse
        # 回填跨表动态字段（合同主币种等），供前端判断异币种展示
        for p in all_payments:
            p.contract_currency = contract.currency
        # 批量填充 payment_account_title
        account_ids = {p.payment_account_id for p in all_payments if p.payment_account_id}
        account_title_map = {}
        if account_ids:
            from app.models.payment_account import PaymentAccount
            accts = db.query(PaymentAccount).filter(PaymentAccount.id.in_(account_ids)).all()
            account_title_map = {a.id: a.title for a in accts}
        for p in all_payments:
            p.payment_account_title = account_title_map.get(p.payment_account_id) if p.payment_account_id else None
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
    def update_payment(db: Session, payment_id: int, payment_data: PaymentUpdate, updated_by: Optional[int] = None) -> Optional[Payment]:
        """更新付款记录。补充凭证时自动从 pending 转为 paid 并参与结算。"""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return None

        # 记录旧值用于审计
        old_values = {
            "status": payment.status,
            "notes": payment.notes,
            "payment_method": payment.payment_method,
            "paid_date": str(payment.paid_date) if payment.paid_date else None,
        }

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
                amount_in_cny = payment.paid_amount_in_cny or payment.paid_amount  # 旧 CNY 数据 paid_amount_in_cny 为 None，原值即 CNY
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

        # 审计日志
        if updated_by:
            try:
                new_values = {k: v for k, v in update_data.items() if v is not None}
                if should_settle:
                    new_values["status"] = "paid"
                AuditService.log(
                    db,
                    user_id=updated_by,
                    action="update",
                    entity_type="payment",
                    entity_id=payment_id,
                    old_values=old_values,
                    new_values=new_values,
                )
            except Exception as e:
                logger.warning("审计日志写入失败: entity=payment, action=update, error=%s", e)

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
                    db, contract, payment.paid_amount, payment.currency,
                    payment.paid_amount_in_cny or 0, payment.paid_date
                )
            else:
                # 收入扣减：按币种折算扣减 paid_amount
                contract.paid_amount_in_cny = (contract.paid_amount_in_cny or 0) - (payment.paid_amount_in_cny or 0)
                if payment.currency == contract.currency:
                    contract.paid_amount = (contract.paid_amount or 0) - (payment.paid_amount or 0)
                else:
                    _, converted = ExchangeRateService.convert_currency(
                        db, payment.paid_amount, payment.currency,
                        contract.currency, payment.paid_date
                    )
                    contract.paid_amount = (contract.paid_amount or 0) - converted
                # 保底为 0，避免历史脏数据导致负数
                contract.paid_amount = max(contract.paid_amount or 0, Decimal('0'))
                contract.paid_amount_in_cny = max(contract.paid_amount_in_cny or 0, Decimal('0'))
                contract.remaining_amount = (contract.total_amount or 0) - (contract.paid_amount or 0)
                contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)

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

    # ──────────────────────────────────────────────────────────────
    # 表单录入专用方法（与 agent 旧路径 create_payment_record 隔离）
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def create_payment_from_form(
        db: Session,
        contract_id: int,
        payload,  # PaymentCreate schema 实例
        created_by: int,
        receipt_path: str = None,
        receipt_file_hash: str = None,
    ) -> Payment:
        """表单创建付款（收入/支出统一入口）。

        - 收入：有凭证 → status=pending + verification_status=pending（等异步校验通过才结算）；
                PaymentCreate schema 已强制收入必须有凭证。
        - 支出：有凭证 → 直接 paid 结算（弱校验提醒，不阻断）；无凭证(no_receipt) → paid 结算。

        Args:
            receipt_path: 已解析的凭证绝对路径（由 API 层从 file_id 解析）。None 表示无凭证。
            receipt_file_hash: 凭证文件哈希（用于去重）。
        """
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        # 期数自动递增（同合同同类型）
        installment_number = PaymentService.get_next_installment_number(db, contract_id, payload.type)

        is_income = payload.type == "income"
        has_receipt = bool(receipt_path)
        # 收入凭证校验：仅 INCOME_RECEIPT_REQUIRED=True 时走 pending→异步校验（现阶段关闭，直接结算）
        # 支出恒 False
        require_verification = is_income and settings.INCOME_RECEIPT_REQUIRED

        # 凭证去重：同一合同下，同一张凭证（按文件哈希）不允许重复录入。
        # 与 AI 路径（file_analyzer / tool_executor）口径一致，scope = 合同内。
        if receipt_path and receipt_file_hash:
            dup = db.query(Payment).filter(
                Payment.contract_id == contract_id,
                Payment.receipt_file_hash == receipt_file_hash,
                Payment.is_deleted == False,
            ).first()
            if dup:
                raise ValueError(
                    f"该凭证已在此合同下录入过（{('收入' if dup.type == 'income' else '支出')}"
                    f" {dup.amount} {dup.currency}），请勿重复录入"
                )

        # payment_method 兜底推导：收入且前端未传/为空时，按所选收款账户的 account_type 推导
        # （bank→bank_transfer 等），避免 payment_method 落 null/unknown。other 及支出留空交 AI 凭证检测。
        payment_method = payload.payment_method
        if not payment_method and is_income and payload.payment_account_id:
            account = db.query(PaymentAccount).filter(
                PaymentAccount.id == payload.payment_account_id
            ).first()
            payment_method = PaymentService._method_from_account_type(
                account.account_type if account else None
            )

        payment = PaymentService.create_payment_with_exchange_rate(
            db=db,
            contract_id=contract_id,
            installment_number=installment_number,
            currency=payload.currency,
            amount=Decimal(str(payload.amount)),
            paid_date=payload.paid_date,
            payment_method=payment_method,
            receipt_image_path=receipt_path,
            receipt_file_hash=receipt_file_hash,
            notes=payload.notes,
            created_by=created_by,
            type=payload.type,
            payee_name=payload.payee_name if payload.type == "expense" else None,
            installment_name=payload.installment_name,
            description=payload.description,
            require_verification=require_verification,
        )

        # 表单新增字段（account / counterparty）独立赋值
        if is_income:
            payment.payment_account_id = payload.payment_account_id
            # 现阶段（开关关闭）：收入无凭证直接打 [无凭证收入] 标记，便于前端识别与将来补凭证
            if not has_receipt:
                from app.core.payment_audit import NO_RECEIPT_INCOME_PREFIX
                base_note = (payment.notes or "").strip()
                payment.notes = f"{NO_RECEIPT_INCOME_PREFIX} {base_note}".strip()
        else:
            payment.counterparty_account = (
                payload.counterparty_account.model_dump(exclude_none=True)
                if payload.counterparty_account else None
            )
            # 无凭证支出：在 notes 开头打 [无凭证支出] 标记，前端据此展示「无凭证」chip。
            # 与 AI 路径（tool_executor）口径一致，避免表单录入的无凭证支出前端无法识别。
            if payload.no_receipt:
                from app.core.payment_audit import NO_RECEIPT_NOTE_PREFIX
                base_note = (payment.notes or "").strip()
                payment.notes = f"{NO_RECEIPT_NOTE_PREFIX} {base_note}".strip()

        # verification_status：收入有凭证→pending（等校验）；无凭证或支出→保持 None（不参与校验流程）
        if is_income and has_receipt:
            payment.verification_status = "pending"
        payment.source = "manual"  # 表单录入标记（区别于 agent 的 screenshot/upload）

        db.commit()
        db.refresh(payment)

        logger.info(
            "表单创建付款: id=%d, contract_id=%d, type=%s, amount=%s, has_receipt=%s, verification=%s",
            payment.id, contract_id, payload.type, payload.amount, has_receipt, payment.verification_status,
        )
        return payment

    @staticmethod
    def update_payment_from_form(
        db: Session,
        payment_id: int,
        payload,  # PaymentUpdate schema 实例
        updated_by: int,
        new_receipt_path: str = None,
        new_receipt_hash: str = None,
        receipt_cleared: bool = False,
    ) -> Optional[Payment]:
        """表单编辑付款。

        核心原则（避免合同金额不一致）：对收入，只要「金额/币种/日期/凭证」任一变化，
        都先反扣旧结算（若已 paid）→ status 回 pending + verification 重置 →
        由 API 层重新投递校验 task，通过后再按新值补结算。

        支出：有无凭证都参与结算，金额/币种变化时同步调整合同支出汇总；凭证变化仅刷新校验提醒。
        """
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return None

        is_income = payment.type == "income"
        contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()

        # 编辑前的快照（反扣必须用旧值，不能用已被改的当前值）
        old_amount = payment.paid_amount or Decimal('0')
        old_currency = payment.currency
        old_paid_amount_in_cny = payment.paid_amount_in_cny or Decimal('0')
        old_paid_date = payment.paid_date
        old_status = payment.status
        was_settled = old_status == "paid"

        # 判断哪些关键字段变化（决定是否需要重算结算）
        amount_changed = payload.amount is not None and Decimal(str(payload.amount)) != old_amount
        currency_changed = payload.currency is not None and payload.currency != old_currency
        date_changed = payload.paid_date is not None and payload.paid_date != old_paid_date
        receipt_changed = bool(receipt_cleared) or bool(new_receipt_path)
        # 收入：金额/币种/日期/凭证任一变化都要重新校验
        income_need_recheck = is_income and (amount_changed or currency_changed or date_changed or receipt_changed)
        # 支出：金额/币种变化需调整合同支出汇总
        expense_need_resettle = (not is_income) and (amount_changed or currency_changed) and was_settled

        # ── 1. 先反扣旧结算（在改字段之前，用旧值反扣）──
        if was_settled and contract and (income_need_recheck or expense_need_resettle):
            PaymentService._reverse_settlement(
                db, contract, payment, is_income,
                old_amount, old_currency, old_paid_amount_in_cny, old_paid_date,
            )

        # ── 2. 普通字段更新 ──
        update_fields = payload.model_dump(exclude_unset=True, exclude_none=True)
        for fld in ("amount", "currency", "paid_date", "payment_method", "installment_name",
                    "description", "notes", "payee_name", "payment_account_id"):
            if fld in update_fields:
                setattr(payment, fld, update_fields[fld])
        if "counterparty_account" in update_fields and not is_income:
            payment.counterparty_account = update_fields["counterparty_account"]

        # payment_method 兜底：收入若仍为空（前端未传或账户类型为 other），按当前收款账户推导。
        # 编辑切账户后 payment_account_id 已更新，这里用最新账户重新推导，保持与账户一致。
        if is_income and not payment.payment_method and payment.payment_account_id:
            account = db.query(PaymentAccount).filter(
                PaymentAccount.id == payment.payment_account_id
            ).first()
            derived = PaymentService._method_from_account_type(
                account.account_type if account else None
            )
            if derived:
                payment.payment_method = derived

        # amount 变了同步 paid_amount + 重算 CNY 等值（金额/币种/日期任一变化都重算）
        if amount_changed or currency_changed:
            new_amount = Decimal(str(payload.amount)) if payload.amount is not None else payment.paid_amount
            payment.paid_amount = new_amount
            eff_currency = payment.currency
            eff_paid_date = payment.paid_date
            if eff_currency == "CNY":
                payment.exchange_rate = Decimal('1.0')
                payment.amount_in_cny = new_amount
                payment.paid_amount_in_cny = new_amount
            else:
                rate, cny = ExchangeRateService.convert_to_cny(db, new_amount, eff_currency, eff_paid_date)
                payment.exchange_rate = rate
                payment.amount_in_cny = cny
                payment.paid_amount_in_cny = cny

        # ── 3. 凭证更新 ──
        if receipt_cleared:
            payment.receipt_image_path = None
            payment.receipt_file_hash = None
        elif new_receipt_path:
            # 凭证去重：换凭证时也要查重（排除自身）
            if new_receipt_hash:
                dup = db.query(Payment).filter(
                    Payment.contract_id == payment.contract_id,
                    Payment.receipt_file_hash == new_receipt_hash,
                    Payment.id != payment.id,
                    Payment.is_deleted == False,
                ).first()
                if dup:
                    raise ValueError(
                        f"该凭证已在此合同下录入过（{('收入' if dup.type == 'income' else '支出')}"
                        f" {dup.amount} {dup.currency}），请勿重复录入"
                    )
            payment.receipt_image_path = new_receipt_path
            payment.receipt_file_hash = new_receipt_hash

        # ── 3.5 支出无凭证标记同步 ──
        # 凭证被清除（变无凭证）→ notes 打 [无凭证支出] 前缀；
        # 凭证从无到有（重新上传）→ 去掉前缀。仅支出，仅凭证确实变化时处理。
        if (not is_income) and receipt_changed:
            from app.core.payment_audit import NO_RECEIPT_NOTE_PREFIX
            base_note = (payment.notes or "")
            has_prefix = base_note.startswith(NO_RECEIPT_NOTE_PREFIX)
            now_no_receipt = not payment.receipt_image_path
            if now_no_receipt and not has_prefix:
                payment.notes = f"{NO_RECEIPT_NOTE_PREFIX} {base_note}".strip()
            elif not now_no_receipt and has_prefix:
                payment.notes = base_note[len(NO_RECEIPT_NOTE_PREFIX):].strip() or None

        # ── 4. 结算/校验状态调整 ──
        if is_income and income_need_recheck:
            # 收入：回退 pending，等重新校验通过后由 task 补结算
            payment.status = "pending"
            payment.verification_status = "pending"
            payment.verification_result = None
            payment.verified_at = None
        elif (not is_income) and expense_need_resettle and contract:
            # 支出：按新值重新累加合同支出汇总
            new_amount_in_cny = payment.paid_amount_in_cny or payment.paid_amount
            PaymentService._add_to_contract_expense(
                db, contract, payment.paid_amount, payment.currency, new_amount_in_cny, payment.paid_date
            )
            # 凭证变化时刷新校验提醒
            if receipt_changed:
                payment.verification_status = None
                payment.verification_result = None
                payment.verified_at = None

        # 支出仅换凭证（金额没变）：不重算结算，只重置校验
        if (not is_income) and receipt_changed and not expense_need_resettle:
            payment.verification_status = None
            payment.verification_result = None
            payment.verified_at = None

        # 审计
        if updated_by:
            try:
                AuditService.log(
                    db, user_id=updated_by, action="update", entity_type="payment",
                    entity_id=payment_id,
                    old_values={"status": old_status, "amount": float(old_amount) if old_amount else None,
                                "verification_status": payment.verification_status},
                    new_values=update_fields,
                )
            except Exception as e:
                logger.warning("审计日志写入失败: entity=payment, action=update(form), error=%s", e)

        db.commit()
        db.refresh(payment)
        logger.info("表单编辑付款: id=%d, income_need_recheck=%s, expense_resettle=%s, receipt_changed=%s → status=%s, verification=%s",
                    payment_id, income_need_recheck, expense_need_resettle, receipt_changed,
                    payment.status, payment.verification_status)
        return payment

    @staticmethod
    def _reverse_settlement(
        db: Session, contract: Contract, payment: Payment, is_income: bool,
        old_amount: Decimal, old_currency: str, old_paid_amount_in_cny: Decimal, old_paid_date,
    ):
        """反向扣减一笔已结算记录的合同汇总（编辑/重校验时回退用）。
        用编辑前的旧值反扣，避免用到已被改写的当前值。"""
        if is_income:
            if old_currency == contract.currency:
                contract.paid_amount = max((contract.paid_amount or 0) - old_amount, Decimal('0'))
            else:
                _, converted = ExchangeRateService.convert_currency(
                    db, old_amount, old_currency, contract.currency, old_paid_date
                )
                contract.paid_amount = max((contract.paid_amount or 0) - converted, Decimal('0'))
            contract.paid_amount_in_cny = max(
                (contract.paid_amount_in_cny or 0) - old_paid_amount_in_cny, Decimal('0')
            )
            contract.remaining_amount = (contract.total_amount or 0) - (contract.paid_amount or 0)
            contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)
        else:
            # 支出反扣
            if old_currency == contract.currency:
                contract.total_expense = max((contract.total_expense or 0) - old_amount, Decimal('0'))
            else:
                _, converted = ExchangeRateService.convert_currency(
                    db, old_amount, old_currency, contract.currency, old_paid_date
                )
                contract.total_expense = max((contract.total_expense or 0) - converted, Decimal('0'))
            contract.total_expense_in_cny = max(
                (contract.total_expense_in_cny or 0) - old_paid_amount_in_cny, Decimal('0')
            )

    @staticmethod
    def _paid_amount_in_cny(db: Session, payment: Payment) -> Decimal:
        """取得付款 CNY 等值；历史空值按付款币种和日期重新折算。"""
        if payment.paid_amount_in_cny is not None:
            return payment.paid_amount_in_cny
        _, amount_in_cny = ExchangeRateService.convert_currency(
            db, payment.paid_amount, payment.currency, 'CNY', payment.paid_date
        )
        payment.paid_amount_in_cny = amount_in_cny
        return amount_in_cny

    @staticmethod
    def manual_confirm_failed_payment(
        db: Session,
        payment_id: int,
        user_id: int,
        reason: str = "操作人确认以表单录入信息为准",
    ) -> Optional[Payment]:
        """人工确认凭证不符的收入记录，按表单录入金额入账。"""
        payment = db.query(Payment).filter(Payment.id == payment_id).with_for_update().first()
        if not payment:
            return None
        if payment.type != "income":
            raise ValueError("仅收入记录支持人工确认")
        if payment.verification_status != "failed":
            raise ValueError("仅凭证不符的记录支持人工确认")
        if payment.status == "paid":
            raise ValueError("该记录已确认入账，请勿重复操作")
        if payment.status != "pending":
            raise ValueError("仅待确认记录支持人工确认")

        contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
        if not contract:
            raise ValueError("合同不存在")

        old_values = {
            "status": payment.status,
            "verification_status": payment.verification_status,
            "verification_result": payment.verification_result,
            "amount": float(payment.paid_amount) if payment.paid_amount is not None else None,
            "currency": payment.currency,
        }
        now = datetime.now(timezone.utc)
        amount_in_cny = PaymentService._paid_amount_in_cny(db, payment)
        PaymentService._add_to_contract_paid(
            db, contract, payment.paid_amount, payment.currency, amount_in_cny, payment.paid_date
        )

        result = dict(payment.verification_result or {})
        result["manual_override"] = True
        result["manual_confirmed_by"] = user_id
        result["manual_confirmed_at"] = now.isoformat()
        result["manual_reason"] = reason
        result["original_verification_status"] = payment.verification_status

        payment.status = "paid"
        payment.verification_status = "passed"
        payment.verification_result = result
        payment.verified_at = now

        audit_entry = AuditLog(
            user_id=user_id,
            action="manual_confirm",
            entity_type="payment",
            entity_id=payment_id,
            old_values=AuditService._json_safe(old_values),
            new_values=AuditService._json_safe({
                "status": payment.status,
                "verification_status": payment.verification_status,
                "manual_override": True,
                "manual_reason": reason,
                "manual_confirmed_at": now.isoformat(),
            }),
        )
        db.add(audit_entry)

        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ValueError("人工确认审计写入失败，操作未生效") from e
        db.refresh(payment)

        logger.info("人工确认入账: payment_id=%d, user_id=%d, amount=%s %s", payment_id, user_id, payment.paid_amount, payment.currency)
        return payment

    @staticmethod
    def settle_verified_payment(db: Session, payment_id: int) -> Optional[Payment]:
        """凭证校验通过后，把 pending 收入转为 paid 并补结算（由 Celery task 调用）。"""
        payment = db.query(Payment).filter(Payment.id == payment_id).with_for_update().first()
        if not payment:
            return None
        if payment.status == "paid":
            return payment  # 幂等：已结算
        if payment.type != "income":
            return payment  # 仅收入走校验结算
        if payment.verification_status != "passed":
            return payment  # 记录已被编辑/重置，等待新一轮校验

        contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
        amount_in_cny = PaymentService._paid_amount_in_cny(db, payment)
        if contract:
            PaymentService._add_to_contract_paid(
                db, contract, payment.paid_amount, payment.currency, amount_in_cny, payment.paid_date
            )
        payment.status = "paid"
        db.commit()
        db.refresh(payment)
        logger.info("校验通过补结算: payment_id=%d, contract_id=%d, amount=%s → paid",
                    payment_id, payment.contract_id, payment.paid_amount)
        return payment

    # ──────────────────────────────────────────────────────────────
    # 对话流（Agent v3）专用方法
    # 跟表单路径区别：
    #   1. 凭证识别 + 匹配判定在工具层同步完成（ReceiptMatcher），不投递异步校验
    #   2. ok 状态直接落 paid + verification_status=passed
    #   3. soft_mismatch 用 create_payment_with_override 走放行通道
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def create_payment_for_dialog(
        db: Session,
        contract_id: int,
        payment_type: str,
        amount: Decimal,
        currency: str,
        paid_date: date,
        payment_method: Optional[str],
        receipt_path: Optional[str],
        receipt_file_hash: Optional[str],
        receipt_data: Optional[dict],
        verification_snapshot: Optional[dict],
        description: Optional[str],
        installment_name: Optional[str],
        notes: Optional[str],
        payee_name: Optional[str],
        payment_account_id: Optional[int],
        counterparty_account: Optional[dict],
        created_by: int,
        no_receipt: bool = False,
    ) -> Payment:
        """对话流创建付款（凭证已同步预校验通过，直落 paid）。

        与 create_payment_from_form 的差别：
          - 收入：跳过 require_verification（直接 paid 结算 + verification_status=passed）
          - 不依赖 Celery 异步校验
          - verification_result 写入 ReceiptMatcher 的对比快照（含 expected/extracted_norm）

        其它（凭证去重、payment_method 兜底、source 标记）保持一致。
        """
        if payment_type not in ("income", "expense"):
            raise ValueError(f"无效的付款类型: {payment_type}")

        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        is_income = payment_type == "income"
        # 收入凭证强制：仅开关开启时拦截（现阶段关闭，对话流可无凭证直落 paid）
        if is_income and not receipt_path and settings.INCOME_RECEIPT_REQUIRED:
            raise ValueError("收入必须有凭证")

        # 凭证去重：同合同同 hash 拦截
        if receipt_path and receipt_file_hash:
            dup = db.query(Payment).filter(
                Payment.contract_id == contract_id,
                Payment.receipt_file_hash == receipt_file_hash,
                Payment.is_deleted == False,
            ).first()
            if dup:
                raise ValueError(
                    f"该凭证已在此合同下录入过（{('收入' if dup.type == 'income' else '支出')}"
                    f" {dup.amount} {dup.currency}），请勿重复录入"
                )

        # payment_method 兜底（收入用账户类型推导，支出留空）
        eff_method = payment_method
        if not eff_method and is_income and payment_account_id:
            account = db.query(PaymentAccount).filter(
                PaymentAccount.id == payment_account_id
            ).first()
            eff_method = PaymentService._method_from_account_type(
                account.account_type if account else None
            )

        installment_number = PaymentService.get_next_installment_number(db, contract_id, payment_type)

        payment = PaymentService.create_payment_with_exchange_rate(
            db=db,
            contract_id=contract_id,
            installment_number=installment_number,
            currency=currency,
            amount=amount,
            paid_date=paid_date,
            payment_method=eff_method,
            receipt_image_path=receipt_path,
            receipt_file_hash=receipt_file_hash,
            receipt_data=receipt_data,
            notes=notes,
            created_by=created_by,
            type=payment_type,
            payee_name=payee_name if not is_income else None,
            installment_name=installment_name,
            description=description,
            require_verification=False,   # ★ 对话流核心：跳过异步校验
        )

        # 表单专属字段补写
        if is_income:
            payment.payment_account_id = payment_account_id
            if receipt_path:
                # 有凭证：写校验快照 + passed
                payment.verification_status = "passed"
                payment.verification_result = verification_snapshot
                payment.verified_at = datetime.now(timezone.utc)
            else:
                # 现阶段无凭证收入：打 [无凭证收入] 标记，verification_status 显式设 passed
                # （已直接 paid 结算，校验状态也应是 passed；避免 UI 出现 "已收 + 待校验" 的双重歧义）
                # notes 里的 [无凭证收入] 前缀已经标识"无凭证"语义，前端 ReceiptChatModal 按此前缀显示"无凭证"标签
                from app.core.payment_audit import NO_RECEIPT_INCOME_PREFIX
                base_note = (payment.notes or "").strip()
                payment.notes = f"{NO_RECEIPT_INCOME_PREFIX} {base_note}".strip()
                payment.verification_status = "passed"
                payment.verified_at = datetime.now(timezone.utc)
        else:
            if counterparty_account:
                payment.counterparty_account = counterparty_account
            if no_receipt:
                from app.core.payment_audit import NO_RECEIPT_NOTE_PREFIX
                base_note = (payment.notes or "").strip()
                payment.notes = f"{NO_RECEIPT_NOTE_PREFIX} {base_note}".strip()
            if verification_snapshot is not None:
                payment.verification_result = verification_snapshot
        payment.source = "screenshot" if receipt_path else "manual"

        db.commit()
        db.refresh(payment)

        logger.info(
            "对话流创建付款: id=%d, contract_id=%d, type=%s, amount=%s, has_receipt=%s, verification=%s",
            payment.id, contract_id, payment_type, amount, bool(receipt_path), payment.verification_status,
        )
        return payment

    @staticmethod
    def create_payment_with_override(
        db: Session,
        contract_id: int,
        payment_type: str,
        amount: Decimal,
        currency: str,
        paid_date: date,
        payment_method: Optional[str],
        receipt_path: Optional[str],
        receipt_file_hash: Optional[str],
        receipt_data: Optional[dict],
        description: Optional[str],
        installment_name: Optional[str],
        notes: Optional[str],
        payee_name: Optional[str],
        payment_account_id: Optional[int],
        counterparty_account: Optional[dict],
        created_by: int,
        operator_name: str,
        operator_role: Optional[str],
        session_id: Optional[str],
        override_reason: str,
        match_status: str,
        extracted_snapshot: Optional[dict],
        user_input_snapshot: Optional[dict],
        expected_snapshot: Optional[dict],
        diff_fields: Optional[list],
        no_receipt: bool = False,
        source: str = "bank_receipt",
    ) -> Payment:
        """对话流：凭证轻微不符（soft_mismatch）或无凭证（manual）手动放行创建付款。

        - 收入：直接 paid + verification_status=passed + manual_override 标记（写入 verification_result）
        - 支出：直接 paid + verification_result 记录原因
        - 同事务写一条 payment_override_audit（业务级审计），失败回滚
        - 同事务写一条 audit_logs（中间件口径，统一 manual_confirm 动作语义）

        source 取值（审计来源）：
          - bank_receipt（默认）：银行凭证/转账截图等正式凭证
          - payment_info_screenshot：付款信息文字截图（聊天记录手敲的转账描述）
          - manual_no_receipt：纯文字无凭证录入（用户口述无凭证支出）
        """
        if not override_reason or not override_reason.strip():
            raise ValueError("放行理由不能为空")
        if match_status not in ("soft_mismatch", "hard_conflict", "manual"):
            raise ValueError(f"非法的放行 match_status: {match_status}")
        if match_status == "hard_conflict":
            # 双保险：工具层应在硬冲突时拒绝调用此方法
            raise ValueError("硬冲突禁止放行")
        if source not in ("bank_receipt", "payment_info_screenshot", "manual_no_receipt"):
            raise ValueError(f"非法的审计来源 source: {source}")

        is_income = payment_type == "income"
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"合同不存在：{contract_id}")

        # 凭证去重
        if receipt_path and receipt_file_hash:
            dup = db.query(Payment).filter(
                Payment.contract_id == contract_id,
                Payment.receipt_file_hash == receipt_file_hash,
                Payment.is_deleted == False,
            ).first()
            if dup:
                raise ValueError(
                    f"该凭证已在此合同下录入过（{('收入' if dup.type == 'income' else '支出')}"
                    f" {dup.amount} {dup.currency}），请勿重复录入"
                )

        eff_method = payment_method
        if not eff_method and is_income and payment_account_id:
            account = db.query(PaymentAccount).filter(
                PaymentAccount.id == payment_account_id
            ).first()
            eff_method = PaymentService._method_from_account_type(
                account.account_type if account else None
            )

        installment_number = PaymentService.get_next_installment_number(db, contract_id, payment_type)
        now = datetime.now(timezone.utc)

        payment = PaymentService.create_payment_with_exchange_rate(
            db=db,
            contract_id=contract_id,
            installment_number=installment_number,
            currency=currency,
            amount=amount,
            paid_date=paid_date,
            payment_method=eff_method,
            receipt_image_path=receipt_path,
            receipt_file_hash=receipt_file_hash,
            receipt_data=receipt_data,
            notes=notes,
            created_by=created_by,
            type=payment_type,
            payee_name=payee_name if not is_income else None,
            installment_name=installment_name,
            description=description,
            require_verification=False,
        )

        if is_income:
            payment.payment_account_id = payment_account_id
            # 放行 = 人工确认通过，状态机与 manual_confirm_failed_payment 对齐：
            # paid 记录的 verification_status 只能是 passed，绝不可能是 failed
            # （failed 仅用于 pending 待人工放行场景）。审计追溯靠 verification_result.manual_override。
            payment.verification_status = "passed"
            payment.verified_at = now
        else:
            if counterparty_account:
                payment.counterparty_account = counterparty_account
            if no_receipt:
                from app.core.payment_audit import NO_RECEIPT_NOTE_PREFIX
                base_note = (payment.notes or "").strip()
                payment.notes = f"{NO_RECEIPT_NOTE_PREFIX} {base_note}".strip()

        # 把"放行印记"写入 verification_result（前端可直接显示"已放行 by X"）
        result = {
            "manual_override": True,
            "manual_override_by": created_by,
            "manual_override_by_name": operator_name,
            "manual_override_at": now.isoformat(),
            "manual_override_reason": override_reason.strip(),
            "match_status": match_status,
            "extracted": extracted_snapshot,
            "user_input": user_input_snapshot,
            "expected": expected_snapshot,
            "diff_fields": diff_fields or [],
        }
        payment.verification_result = result
        payment.source = "screenshot" if receipt_path else "manual"

        # 写业务级审计表
        audit_row = PaymentOverrideAudit(
            payment_id=payment.id,
            operator_id=created_by,
            operator_name=operator_name,
            operator_role=operator_role,
            session_id=session_id,
            match_status=match_status,
            override_reason=override_reason.strip(),
            extracted_snapshot=AuditService._json_safe(extracted_snapshot or {}),
            user_input_snapshot=AuditService._json_safe(user_input_snapshot or {}),
            expected_snapshot=AuditService._json_safe(expected_snapshot or {}),
            diff_fields=AuditService._json_safe({"items": diff_fields or []}).get("items"),
            source=source,
        )
        db.add(audit_row)

        # 同时写 audit_logs，与既有 manual_confirm 流程口径一致
        audit_log_row = AuditLog(
            user_id=created_by,
            action="manual_override_create",
            entity_type="payment",
            entity_id=payment.id,
            old_values=None,
            new_values=AuditService._json_safe({
                "match_status": match_status,
                "manual_override_reason": override_reason.strip(),
                "amount": float(amount),
                "currency": currency,
                "type": payment_type,
            }),
        )
        db.add(audit_log_row)

        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ValueError("放行审计写入失败，操作未生效") from e
        db.refresh(payment)

        logger.info(
            "对话流放行创建付款: id=%d, status=%s, operator=%s, reason=%s",
            payment.id, match_status, operator_name, override_reason[:50],
        )
        return payment

