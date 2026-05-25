"""
FastAPI应用主入口
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.api.v1 import auth, customers, contracts, payments, agent, files, exchange_rates
from app.core.exceptions import AppException

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="企业级合同管理与智能客服系统",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.code,
        content={"detail": exc.message, "code": exc.code, "details": exc.details}
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
