"""
FastAPI应用主入口
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.api.v1 import auth, customers, contracts, payments, agent, files, exchange_rates
from app.core.exceptions import AppException
from app.core.middleware import RequestLoggingMiddleware, AuditLogMiddleware
from app.core.logging import setup_logging

# 初始化结构化日志
setup_logging()
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
    logger.info(
        "app_starting",
        app_name=settings.APP_NAME,
        env=settings.APP_ENV,
    )


@app.on_event("shutdown")
async def on_shutdown():
    """应用关闭时的清理"""
    logger.info("app_shutting_down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
