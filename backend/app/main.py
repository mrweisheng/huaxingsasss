"""
FastAPI应用主入口
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import auth, customers, contracts, payments, agent, files, exchange_rates, users, stats
from app.core.exceptions import AppException
from app.core.middleware import RequestLoggingMiddleware, AuditLogMiddleware
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="企业级合同管理与智能客服系统",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuditLogMiddleware)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning("app_exception: status=%s, message=%s, path=%s",
                   exc.code, exc.message, request.url.path)
    return JSONResponse(
        status_code=exc.code,
        content={"detail": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception: path=%s, error=%s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试", "code": 500}
    )


app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["认证"])
app.include_router(customers.router, prefix=f"{settings.API_V1_STR}/customers", tags=["客户管理"])
app.include_router(contracts.router, prefix=f"{settings.API_V1_STR}/contracts", tags=["合同管理"])
app.include_router(payments.router, prefix=f"{settings.API_V1_STR}/payments", tags=["付款管理"])
app.include_router(agent.router, prefix=f"{settings.API_V1_STR}/agent", tags=["智能问答"])
app.include_router(files.router, prefix=f"{settings.API_V1_STR}/files", tags=["文件管理"])
app.include_router(exchange_rates.router, prefix=f"{settings.API_V1_STR}/exchange-rates", tags=["汇率管理"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["用户管理"])
app.include_router(stats.router, prefix=f"{settings.API_V1_STR}/stats", tags=["财务统计"])


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "0.1.0"}


@app.on_event("startup")
async def on_startup():
    # Phase 1 重构：放弃 alembic，表结构由 scripts/init_db.py 一次性建好
    # LangGraph checkpoint 表由 init_checkpointer() 内部 setup() 自动创建
    from app.ai.orchestrator.checkpointer import init_checkpointer
    await init_checkpointer()
    logger.info("app_starting: app=%s, env=%s", settings.APP_NAME, settings.APP_ENV)


@app.on_event("shutdown")
async def on_shutdown():
    from app.ai.orchestrator.checkpointer import close_checkpointer
    await close_checkpointer()
    logger.info("app_shutting_down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
