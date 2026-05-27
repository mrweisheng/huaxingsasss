"""
基于 Redis 的速率限制器
"""
import time
import structlog
from typing import Optional
from fastapi import HTTPException, Request
from app.config import settings

logger = structlog.get_logger()


class RateLimiter:
    """简单的滑动窗口速率限制器"""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._memory_store: dict[str, list[float]] = {}  # fallback when Redis unavailable
        self._redis_client = None

    def _init_redis(self):
        """延迟初始化 Redis 连接"""
        if self._redis_client is None:
            try:
                import redis
                self._redis_client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                    decode_responses=True
                )
                self._redis_client.ping()
            except Exception as e:
                logger.warning("rate_limiter_redis_unavailable", error=str(e))
                self._redis_client = None  # Redis 不可用时回退到内存存储

    async def check(self, key: str) -> None:
        """
        检查是否超出速率限制

        Args:
            key: 限流键（如 IP 地址）

        Raises:
            HTTPException 429: 超出限制
        """
        now = time.time()
        window_start = now - self.window_seconds

        self._init_redis()

        if self._redis_client:
            try:
                pipeline = self._redis_client.pipeline()
                pipeline.zremrangebyscore(key, 0, window_start)
                pipeline.zcard(key)
                pipeline.zadd(key, {str(now): now})
                pipeline.expire(key, self.window_seconds)
                _, count, _, _ = pipeline.execute()

                if count >= self.max_attempts:
                    raise HTTPException(
                        status_code=429,
                        detail=f"请求过于频繁，请 {self.window_seconds} 秒后再试"
                    )
                return
            except Exception:
                pass  # Redis 出错，回退到内存存储

        # 内存 fallback
        records = self._memory_store.get(key, [])
        records = [t for t in records if t > window_start]

        if len(records) >= self.max_attempts:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，请 {self.window_seconds} 秒后再试"
            )

        records.append(now)
        self._memory_store[key] = records


# 登录速率限制器：每分钟最多 5 次尝试
login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
