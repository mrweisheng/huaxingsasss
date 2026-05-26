"""
请求中间件：审计日志自动记录 + 请求ID注入
"""
import uuid
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.session import SessionLocal
from app.services.audit_service import AuditService
import structlog

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    - 为每个请求注入 request_id
    - 记录请求耗时
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()

        response = await call_next(request)

        elapsed = time.time() - start_time
        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        response.headers["X-Request-ID"] = request_id
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    审计日志中间件
    自动记录所有写操作 (POST/PUT/PATCH/DELETE) 到 audit_logs 表
    """

    # 需要审计的操作映射
    MUTATING_METHODS = {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}

    # 跳过审计的路径前缀
    SKIP_PATHS = ("/health", "/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 非写操作或跳过路径不处理
        if request.method not in self.MUTATING_METHODS:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in self.SKIP_PATHS):
            return await call_next(request)

        # 先执行请求
        response = await call_next(request)

        # 仅记录 2xx 成功响应
        if response.status_code < 200 or response.status_code >= 300:
            return response

        # 尝试获取用户和审计所需信息
        try:
            user = getattr(request.state, "user", None)
            if user and hasattr(user, "id"):
                db = SessionLocal()
                try:
                    AuditService.log(
                        db=db,
                        user_id=user.id,
                        action=self.MUTATING_METHODS[request.method],
                        entity_type=request.url.path.split("/")[-1],
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                    )
                finally:
                    db.close()
        except Exception:
            pass  # 审计日志失败不影响业务请求

        return response
