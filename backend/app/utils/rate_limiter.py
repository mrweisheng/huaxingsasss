"""
基于 Redis 的速率限制器
"""
import logging
import time
from typing import Optional
from fastapi import HTTPException, Request
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._memory_store: dict[str, list[float]] = {}
        self._redis_client = None

    def _init_redis(self):
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
                logger.warning("rate_limiter_redis_unavailable: %s", str(e))
                self._redis_client = None

    async def check(self, key: str) -> None:
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
                # Redis 暂时不可用时降级到内存计数，异常详情写日志便于线上排障
                logger.debug("rate_limiter: Redis pipeline 失败，降级内存计数", exc_info=True)
                pass

        records = self._memory_store.get(key, [])
        records = [t for t in records if t > window_start]

        if len(records) >= self.max_attempts:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，请 {self.window_seconds} 秒后再试"
            )

        records.append(now)
        self._memory_store[key] = records


login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)