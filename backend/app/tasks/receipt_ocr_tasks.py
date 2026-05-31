"""
付款凭证 OCR 异步任务
"""
import asyncio
import logging
from celery import current_task
from app.tasks.celery_app import celery_app
from app.ai.llm_client import SiliconFlowClient
from app.db.session import SessionLocal
from app.models.payment import Payment
from app.services.exchange_rate_service import ExchangeRateService
from decimal import Decimal
from datetime import date

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def ocr_receipt_task(self, payment_id: int, file_path: str):
    """
    异步识别付款凭证

    Args:
        payment_id: 付款记录 ID
        file_path: 凭证图片本地路径
    """
    db = SessionLocal()
    try:
        logger.info("凭证OCR开始: payment_id=%d, file=%s", payment_id, file_path)
        current_task.update_state(state="PROCESSING", meta={"progress": 30})

        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            logger.warning("付款记录不存在: payment_id=%d", payment_id)
            return {"error": "Payment not found"}

        current_task.update_state(state="PROCESSING", meta={"progress": 60})

        client = SiliconFlowClient()
        result = asyncio.run(client.parse_contract_image(file_path))

        recognized_data = result["data"]

        # 更新支付记录
        if recognized_data.get("paid_amount"):
            payment.paid_amount = Decimal(str(recognized_data["paid_amount"]))
        if recognized_data.get("paid_date"):
            try:
                payment.paid_date = date.fromisoformat(recognized_data["paid_date"])
            except (ValueError, TypeError):
                pass
        if recognized_data.get("payment_method"):
            payment.payment_method = recognized_data["payment_method"]

        # 根据付款日期查询汇率
        if payment.paid_date and payment.currency != "CNY":
            rate, amount_cny = ExchangeRateService.convert_to_cny(
                db, payment.paid_amount, payment.currency, payment.paid_date
            )
            payment.exchange_rate = rate

        # 更新状态
        if payment.paid_amount and payment.paid_amount >= payment.amount:
            payment.status = "paid"

        db.commit()

        logger.info("凭证OCR完成: payment_id=%d, status=%s", payment_id, payment.status)
        return {
            "payment_id": payment_id,
            "status": "completed",
            "recognized": recognized_data,
        }

    except Exception as exc:
        logger.error("凭证OCR失败: payment_id=%d, error=%s", payment_id, exc, exc_info=True)
        raise self.retry(exc=exc)

    finally:
        db.close()
