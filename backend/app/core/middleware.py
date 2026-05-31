"""
请求中间件：审计日志自动记录 + 请求ID注入
"""
import logging
import uuid
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.session import SessionLocal
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()

        response = await call_next(request)

        elapsed = time.time() - start_time
        logger.info("request_completed: id=%s, method=%s, path=%s, status=%s, elapsed=%sms",
                    request_id, request.method, request.url.path,
                    response.status_code, round(elapsed * 1000, 2))

        response.headers["X-Request-ID"] = request_id
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    MUTATING_METHODS = {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}
    SKIP_PATHS = ("/health", "/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in self.MUTATING_METHODS:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in self.SKIP_PATHS):
            return await call_next(request)

        response = await call_next(request)

        if response.status_code < 200 or response.status_code >= 300:
            return response

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
            pass

        return response