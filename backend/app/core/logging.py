"""
结构化日志配置

使用 structlog 输出 JSON 格式日志，便于 ELK 等日志系统收集
"""
import os
import sys
import structlog
from app.config import settings


def setup_logging():
    """
    初始化结构化日志

    开发环境：带颜色的可读格式
    生产环境：JSON 格式，便于日志收集系统解析
    """
    is_dev = settings.APP_ENV == "development"

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_dev:
        # 开发环境：控制台彩色输出
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]
    else:
        # 生产环境：JSON 输出
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 将标准 logging 重定向到 structlog
    import logging
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.LOG_LEVEL)

    # 屏蔽第三方 HTTP 库的连接细节日志
    for name in ("httpx", "openai", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)
