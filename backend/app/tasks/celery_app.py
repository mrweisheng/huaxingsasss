"""
Celery 应用配置

Broker: Redis (通过 .env 配置 REDIS_HOST / REDIS_PORT)
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "contract_system",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.contract_tasks",
        "app.tasks.receipt_ocr_tasks",
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
