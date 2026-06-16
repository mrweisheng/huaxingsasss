"""
凭证异步校验任务

表单录入收入后，提交即落库 pending + verification_status=pending；
本任务由 Celery 异步执行：用 FileAnalyzer 提取凭证金额/付款方，与表单填写比对，
通过则补结算(pending→paid)，不符则标红(verification_status=failed)不结算。

支出有凭证时也可调用本任务做弱校验提醒（不阻断结算，仅回填 verification_result 供展示）。
"""
import logging
import os
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.payment import Payment
from app.models.contract import Contract
from app.services.file_analyzer import FileAnalyzer
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

# 校验阈值（可后续抽到配置）
AMOUNT_TOLERANCE = Decimal("0.02")   # 金额允许 ±2% 偏差
LOW_CONFIDENCE_THRESHOLD = 0.6       # VL 置信度低于此值判"存疑"


@celery_app.task(name="app.tasks.receipt_verification_tasks.verify_receipt", bind=True, max_retries=2)
def verify_receipt(self, payment_id: int):
    """对一笔 payment 的凭证做异步校验并回填结果。

    - 收入：通过→settle_verified_payment 补结算；不符→failed 不结算；存疑→保持 pending 待人工。
    - 支出：仅回填 verification_result 弱提醒，不改变 status。
    """
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            logger.warning("verify_receipt: payment %s 不存在", payment_id)
            return {"status": "not_found", "payment_id": payment_id}

        if not payment.receipt_image_path or not os.path.isfile(payment.receipt_image_path):
            # 凭证文件丢失：标 failed，原因记明
            # 防御：若该收入记录已 paid 结算（异常状态），先反扣避免合同金额虚高
            _settle_back_if_paid(db, payment)
            _record_failure(payment, reason="凭证文件不存在或已丢失")
            db.commit()
            return {"status": "missing_file", "payment_id": payment_id}

        # 1. VL 提取凭证信息
        try:
            analysis = FileAnalyzer.analyze(
                file_path=payment.receipt_image_path,
                file_name=os.path.basename(payment.receipt_image_path),
                purpose="receipt",
                contract_id=payment.contract_id,
                skip_duplicate_check=True,  # 创建时已去重，校验阶段跳过
            )
        except Exception as e:
            logger.exception("verify_receipt: FileAnalyzer 异常 payment_id=%s", payment_id)
            raise self.retry(exc=e, countdown=60)

        if not analysis.get("success"):
            _settle_back_if_paid(db, payment)
            _record_failure(payment, reason=f"凭证识别失败：{analysis.get('error', '未知')}")
            db.commit()
            return {"status": "analyze_failed", "payment_id": payment_id}

        extracted = analysis.get("data") or {}
        confidence = float(extracted.get("confidence") or 0)

        # 2. 取表单期望值（金额/币种/付款方）
        expected_amount = payment.paid_amount
        expected_currency = payment.currency
        expected_payer = _get_contract_customer_name(db, payment.contract_id)

        ext_amount = _to_decimal(extracted.get("amount"))
        ext_currency = extracted.get("currency")
        ext_payer = extracted.get("payer_name")

        # 3. 比对
        amount_match = _amount_matches(expected_amount, ext_amount)
        currency_match = (ext_currency in (None, "", expected_currency)) if ext_currency else True
        payer_match = _name_matches(expected_payer, ext_payer)

        verification_result = {
            "expected": {
                "amount": float(expected_amount) if expected_amount is not None else None,
                "currency": expected_currency,
                "payer": expected_payer,
            },
            "extracted": {
                "amount": float(ext_amount) if ext_amount is not None else None,
                "currency": ext_currency,
                "payer_name": ext_payer,
            },
            "match": {"amount": amount_match, "currency": currency_match, "payer": payer_match},
            "confidence": confidence,
        }

        is_income = payment.type == "income"

        # 4. 判定
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            # 存疑：不置红，保持 pending 待人工核对（仅收入；支出不影响）
            verification_result["reason"] = f"凭证识别置信度偏低({confidence:.2f})，请人工核对"
            payment.verification_result = verification_result
            payment.verification_status = "pending"  # 维持待校验
            payment.verified_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("校验存疑: payment_id=%s, confidence=%.2f", payment_id, confidence)
            return {"status": "uncertain", "payment_id": payment_id}

        passed = amount_match and currency_match
        verification_result["reason"] = "凭证与表单一致" if passed else _build_mismatch_reason(
            amount_match, currency_match, payer_match
        )
        payment.verification_result = verification_result
        payment.verified_at = datetime.now(timezone.utc)

        if is_income:
            if passed:
                payment.verification_status = "passed"
                # 关键：校验通过补结算 pending→paid
                db.commit()
                db.refresh(payment)
                PaymentService.settle_verified_payment(db, payment_id)
                logger.info("校验通过并结算: payment_id=%s", payment_id)
                return {"status": "passed_settled", "payment_id": payment_id}
            else:
                # 不符：标红不结算。防御性反扣（正常收入 paid 都需校验通过，此处多为历史数据）
                _settle_back_if_paid(db, payment)
                payment.verification_status = "failed"
                db.commit()
                logger.info("校验不符(标红不结算): payment_id=%s, reason=%s",
                            payment_id, verification_result["reason"])
                return {"status": "failed", "payment_id": payment_id, "reason": verification_result["reason"]}
        else:
            # 支出：弱校验，仅回填结果，不改变 status/结算
            payment.verification_status = "passed" if passed else "failed"
            db.commit()
            logger.info("支出凭证弱校验: payment_id=%s, passed=%s", payment_id, passed)
            return {"status": "expense_weak_check", "payment_id": payment_id, "passed": passed}

    except Exception as e:
        logger.exception("verify_receipt 任务异常: payment_id=%s", payment_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=120 * (self.request.retries + 1))
        return {"status": "error", "payment_id": payment_id, "error": str(e)}
    finally:
        db.close()


# ── 辅助函数 ──

def _settle_back_if_paid(db, payment: Payment):
    """若一笔收入已 paid 结算，反向扣减合同已收金额并回退 pending。
    用于校验失败/凭证丢失时的防御性处理（正常 pending→failed 不触发，主要兜底历史数据）。"""
    if payment.status != "paid" or payment.type != "income":
        return
    contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
    if contract:
        PaymentService._reverse_settlement(
            db, contract, payment, is_income=True,
            old_amount=payment.paid_amount or Decimal('0'),
            old_currency=payment.currency,
            old_paid_amount_in_cny=payment.paid_amount_in_cny or Decimal('0'),
            old_paid_date=payment.paid_date,
        )
    payment.status = "pending"


def _record_failure(payment: Payment, reason: str):
    payment.verification_status = "failed"
    payment.verification_result = {"reason": reason, "match": {"amount": False, "payer": False}}
    payment.verified_at = datetime.now(timezone.utc)


def _get_contract_customer_name(db, contract_id: int) -> str | None:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract and contract.customer:
        return contract.customer.name
    return None


def _to_decimal(val) -> Decimal | None:
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def _amount_matches(expected: Decimal | None, extracted: Decimal | None) -> bool:
    """金额比对：允许 ±AMOUNT_TOLERANCE（默认2%）偏差，兼容手填/识别微小误差。"""
    if expected is None or extracted is None:
        return False
    if expected == 0:
        return extracted == 0
    diff_ratio = abs(extracted - expected) / abs(expected)
    return diff_ratio <= AMOUNT_TOLERANCE


def _name_matches(expected: str | None, extracted: str | None) -> bool:
    """付款方模糊匹配：包含关系或去掉空格后相等，兼容别名/简写/OCR误差。"""
    if not expected or not extracted:
        # 表单侧无客户名时不以此项判定失败
        return True
    a = expected.strip().lower()
    b = extracted.strip().lower()
    if not a or not b:
        return True
    # 互相包含（覆盖"胡少楝" vs "胡少楝（XX公司）"）
    return a in b or b in a or _normalize_name(a) == _normalize_name(b)


def _normalize_name(s: str) -> str:
    import re
    return re.sub(r"[\s（）()·\-_]", "", s)


def _build_mismatch_reason(amount_ok: bool, currency_ok: bool, payer_ok: bool) -> str:
    reasons = []
    if not amount_ok:
        reasons.append("金额不一致")
    if not currency_ok:
        reasons.append("币种不一致")
    if not payer_ok:
        reasons.append("付款方不一致")
    return "、".join(reasons) + "，请核对凭证或表单填写"
