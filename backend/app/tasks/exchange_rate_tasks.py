"""
汇率自动同步定时任务

每天北京时间 00:30 自动同步最新汇率到数据库。
数据来源：广发银行（主） + 中国银行LLM解析（兜底）
"""
import asyncio
import logging
from datetime import date

from decimal import Decimal

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.exchange_rate_fetcher import fetch_exchange_rates
from app.services.exchange_rate_service import ExchangeRateService

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.exchange_rate_tasks.sync_daily_rates", bind=True, max_retries=3)
def sync_daily_rates(self):
    """
    Celery 入口：获取汇率 → 存入数据库

    流程：
    1. 调用 fetch_exchange_rates() 获取 HKD/CNY 和 USD/CNY 汇率
    2. 遍历两种货币，存入或更新数据库
    3. 失败时重试（最多3次）

    Returns:
        dict: {status, message, date, details}
    """
    logger.info("开始执行每日汇率同步任务...")
    today = date.today()

    db = SessionLocal()
    try:
        rates = asyncio.run(fetch_exchange_rates())

        if rates["hkdcny"] is None and rates["usdcny"] is None:
            logger.error("汇率获取失败：两个货币对都没有数据")
            raise self.retry(exc=Exception("汇率获取全部失败"), countdown=300)

        result = _save_rates_to_db(db, rates, today)
        logger.info("汇率同步完成: %s", result["message"])
        return result

    except Exception as e:
        logger.error("汇率同步任务异常: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=300 * (self.request.retries + 1))
        return {
            "status": "failure",
            "message": f"汇率同步失败（已重试{self.max_retries}次）: {str(e)}",
            "date": str(today),
            "details": {},
        }
    finally:
        db.close()


def _save_rates_to_db(db, rates: dict, today: date) -> dict:
    """
    将汇率数据存入数据库。

    逻辑：
    - 如果当日已有相同汇率，跳过（避免重复写入）
    - 如果汇率变化，更新记录
    - 如果当日无记录，新增记录

    Args:
        db: SQLAlchemy 会话
        rates: {"hkdcny": float, "usdcny": float, "source": str, "date": str}
        today: 当前日期

    Returns:
        {"status": str, "message": str, "details": dict}
    """
    saved_count = 0
    skipped = []
    errors = []
    details = {}

    source = rates.get("source", "unknown")

    for currency_code, rate_key in [("HKD", "hkdcny"), ("USD", "usdcny")]:
        rate_value = rates.get(rate_key)

        if rate_value is None:
            details[f"{currency_code}/CNY"] = {"skipped": "未获取到汇率"}
            continue

        rate_decimal = Decimal(str(rate_value))

        existing = ExchangeRateService.get_exchange_rate_record(
            db, currency_code, "CNY", today
        )

        if existing and existing.rate == rate_decimal:
            skipped.append(f"{currency_code}/CNY: 今日已有相同汇率 ({rate_value})")
            details[f"{currency_code}/CNY"] = {
                "action": "skipped",
                "rate": float(rate_decimal),
                "source": source,
            }
            continue

        try:
            ExchangeRateService.update_exchange_rate(
                db=db,
                from_currency=currency_code,
                to_currency="CNY",
                rate=rate_decimal,
                rate_date=today,
                source=source,
            )
            saved_count += 1
            action = "更新" if existing else "新增"
            logger.info(f"{action}汇率 {currency_code}/CNY = {rate_value} ({today}, {source})")
            details[f"{currency_code}/CNY"] = {
                "action": action.lower(),
                "rate": float(rate_decimal),
                "source": source,
            }
        except Exception as e:
            err_msg = f"{currency_code}/CNY: {str(e)}"
            errors.append(err_msg)
            logger.error(err_msg)
            details[f"{currency_code}/CNY"] = {"error": str(e)}

    if errors:
        status = "partial_failure"
        message = f"部分成功: 保存{saved_count}条，跳过{len(skipped)}条，失败{len(errors)}条"
    elif saved_count > 0:
        status = "success"
        message = f"同步成功: 新增/更新了 {saved_count} 条汇率（来源: {source}）"
    else:
        status = "no_change"
        message = f"无需更新: 今日汇率已存在且一致"

    return {
        "status": status,
        "message": message,
        "date": str(today),
        "details": details,
    }