"""
FastAPI应用主入口
"""
# ⚠️ setup_logging 必须在所有业务模块导入之前执行，
# 否则 tools.py / agent.py 的 structlog.get_logger() 拿到空配置
from app.core.logging import setup_logging
setup_logging()

import structlog

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import AppException
from app.core.middleware import RequestLoggingMiddleware, AuditLogMiddleware

from app.api.v1 import auth, customers, contracts, payments, agent, files, exchange_rates

logger = structlog.get_logger()

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="企业级合同管理与智能客服系统",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 中间件（允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件（记录请求耗时、注入 request_id）
app.add_middleware(RequestLoggingMiddleware)

# 审计日志中间件（自动记录写操作）
app.add_middleware(AuditLogMiddleware)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning(
        "app_exception",
        status_code=exc.code,
        message=exc.message,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.code,
        content={"detail": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试", "code": 500}
    )


# 路由注册
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["认证"])
app.include_router(customers.router, prefix=f"{settings.API_V1_STR}/customers", tags=["客户管理"])
app.include_router(contracts.router, prefix=f"{settings.API_V1_STR}/contracts", tags=["合同管理"])
app.include_router(payments.router, prefix=f"{settings.API_V1_STR}/payments", tags=["付款管理"])
app.include_router(agent.router, prefix=f"{settings.API_V1_STR}/agent", tags=["智能问答"])
app.include_router(files.router, prefix=f"{settings.API_V1_STR}/files", tags=["文件管理"])
app.include_router(exchange_rates.router, prefix=f"{settings.API_V1_STR}/exchange-rates", tags=["汇率管理"])


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "0.1.0"}


@app.on_event("startup")
async def on_startup():
    """应用启动时的初始化"""
    # 自动执行数据库迁移
    _run_migrations()

    logger.info(
        "app_starting",
        app_name=settings.APP_NAME,
        env=settings.APP_ENV,
    )


def _run_migrations():
    """启动时自动执行 Alembic 迁移"""
    import os
    from alembic.config import Config
    from alembic import command

    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        migrations_dir = os.path.join(backend_dir, "migrations")
        alembic_cfg_path = os.path.join(migrations_dir, "alembic.ini")

        alembic_cfg = Config(alembic_cfg_path)
        # 显式设置绝对路径，避免相对路径解析错误
        alembic_cfg.set_main_option("script_location", migrations_dir)

        logger.info("running_database_migrations", migrations_dir=migrations_dir)
        command.upgrade(alembic_cfg, "head")
        logger.info("database_migrations_applied")
    except Exception as e:
        logger.error("database_migration_failed", error=str(e), exc_info=True)
        raise


@app.on_event("shutdown")
async def on_shutdown():
    """应用关闭时的清理"""
    logger.info("app_shutting_down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
