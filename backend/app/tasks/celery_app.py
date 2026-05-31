"""
Celery 应用配置

Broker: Redis (通过 .env 配置 REDIS_HOST / REDIS_PORT)
"""
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "contract_system",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.contract_tasks",
        "app.tasks.receipt_ocr_tasks",
        "app.tasks.cleanup_tasks",
        "app.tasks.exchange_rate_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes
)

celery_app.conf.beat_schedule = {
    "cleanup-temp-files": {
        "task": "app.tasks.cleanup_tasks.cleanup_temp_files",
        "schedule": crontab(minute=0, hour=3),  # 每天凌晨3点
        "args": (24,),
    },
    "sync-daily-exchange-rates": {
        "task": "app.tasks.exchange_rate_tasks.sync_daily_rates",
        "schedule": crontab(minute=30, hour=0),  # 每天凌晨0:30
    },
}


# Worker 启动时初始化日志配置，确保 task 中的 logger 输出到 stdout
@celery_app.on_after_configure.connect
def setup_celery_logging(sender, **kwargs):
    from app.core.logging import setup_logging
    setup_logging()
