"""
FastAPI应用主入口
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import auth, customers, contracts, payments, agent, files, exchange_rates, users, stats, payment_accounts
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
    # 不做来源限制：allow_credentials=True 与 allow_origins=["*"] 互斥（W3C CORS 规范禁止），
    # 必须用 allow_origin_regex=".*" 让中间件把请求 Origin 原样回填，等价于"不限来源"
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
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
app.include_router(payment_accounts.router, prefix=f"{settings.API_V1_STR}/payment-accounts", tags=["收款账户"])
app.include_router(stats.router, prefix=f"{settings.API_V1_STR}/stats", tags=["财务统计"])


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "0.1.0"}


@app.on_event("startup")
async def on_startup():
    # 业务表由用户手动执行 SQL 维护（禁止 alembic 自动迁移）
    # LangGraph checkpoint 表由 init_checkpointer() 内部 setup() 自动创建
    from app.ai.orchestrator.checkpointer import init_checkpointer
    await init_checkpointer()

    # 进程级注册 HEIF/HEIC 解码器：让 PIL.Image.open() 在任何路径下都能识别
    # iPhone 默认拍照格式。注册是幂等的；任何异常都不应阻断应用启动，
    # 注册失败时上传端点会自动落到 400 友好提示。
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        logger.info("pillow_heif_registered")
    except Exception as exc:
        logger.warning("pillow_heif_register_failed: %s", exc)

    # LangSmith 可观测性（Phase 2.7）：将 pydantic settings 同步到 os.environ，
    # langsmith SDK 从环境变量读取追踪配置，设置后 LangGraph 节点自动埋点
    import os
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        logger.info("langsmith_tracing_enabled: project=%s", settings.LANGCHAIN_PROJECT)
    else:
        logger.info("langsmith_tracing_disabled")

    logger.info("app_starting: app=%s, env=%s", settings.APP_NAME, settings.APP_ENV)


@app.on_event("shutdown")
async def on_shutdown():
    from app.ai.orchestrator.checkpointer import close_checkpointer
    await close_checkpointer()
    logger.info("app_shutting_down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
