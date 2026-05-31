"""
日志配置

核心原则：不依赖 logging.basicConfig()（会被 uvicorn/celery 劫持导致失效），
改为显式配置 root logger 的 StreamHandler，确保所有日志输出到 stdout，
被 systemd/journald 正确捕获。
"""
import logging
import sys
from app.config import settings

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_logging():
    """
    初始化日志配置。

    幂等：多次调用只会配置一次。
    显式给 root logger 添加 stdout handler，不依赖 basicConfig。
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 创建 stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)

    # 显式配置 root logger（不用 basicConfig，避免被 uvicorn/celery 覆盖）
    root = logging.getLogger()
    root.setLevel(level)
    # 清除已有 handler（可能是 uvicorn 或 celery 留下的）
    root.handlers.clear()
    root.addHandler(handler)

    # 降噪：第三方库只输出 WARNING 及以上
    for name in ("httpx", "openai", "httpcore", "urllib3", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn.error 保持 INFO，能看到启动/关闭日志
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
