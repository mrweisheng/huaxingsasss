"""
日志配置

策略：只配置 app logger，设 propagate=False，与 root logger 完全隔离。
uvicorn/alembic/Celery 怎么改 root logger 都与我们无关。
所有 app.* 子 logger 的日志自动传播到 app logger → stdout。
"""
import logging
import sys
from app.config import settings

_initialized = False


def setup_logging():
    global _initialized
    if _initialized:
        return
    _initialized = True

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)

    # 只配我们自己的 app logger，不碰 root logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.propagate = False  # 不传播到 root，彻底隔离

    # 降噪：第三方库
    for name in ("httpx", "openai", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
