from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import cast

from fastapi import Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int


class RateLimiter:
    """Fixed-window limiter with Redis shared state and an in-process fallback.

    The fallback keeps authentication usable when Redis is down, but it is not shared
    between processes. Production uses Redis.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis: Redis | None = None
        self._memory: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()
        if redis_url:
            self._redis = Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        if self._redis is not None:
            try:
                return self._hit_redis(key, limit, window_seconds)
            except RedisError:
                logger.warning("rate limiter fell back to memory: redis unavailable")

        return self._hit_memory(key, limit, window_seconds)

    def _hit_redis(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        if self._redis is None:
            raise RuntimeError("Redis rate limiting was used without a configured client.")
        redis_key = f"ratelimit:{key}"
        current = cast(int, self._redis.incr(redis_key))
        if current == 1:
            self._redis.expire(redis_key, window_seconds)
        ttl = cast(int, self._redis.ttl(redis_key))
        retry_after = ttl if ttl > 1 else 1
        return RateLimitResult(allowed=current <= limit, retry_after=retry_after)

    def _hit_memory(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.monotonic())
        window_start = now - (now % window_seconds)
        reset_at = window_start + window_seconds

        with self._lock:
            stored_window, count = self._memory.get(key, (window_start, 0))
            if stored_window != window_start:
                count = 0
            count += 1
            self._memory[key] = (window_start, count)

            if len(self._memory) > 10_000:
                self._memory = {k: v for k, v in self._memory.items() if v[0] >= window_start}

        return RateLimitResult(
            allowed=count <= limit,
            retry_after=max(reset_at - int(time.time()), 1),
        )

    def reset(self) -> None:
        with self._lock:
            self._memory.clear()
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter("ratelimit:*", count=100):
                    self._redis.delete(key)
            except RedisError:
                pass


_limiter: RateLimiter | None = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            _limiter = RateLimiter(settings.redis_url or None)
        return _limiter


def reset_rate_limiter() -> None:
    global _limiter
    with _limiter_lock:
        if _limiter is not None:
            _limiter.reset()
        _limiter = None


def enforce_auth_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    key = f"auth:{client_host}:{request.url.path}"
    result = get_rate_limiter().hit(key, settings.auth_rate_limit_per_minute, 60)
    if not result.allowed:
        raise AppError(
            429,
            "rate_limited",
            "Too many attempts. Please wait a minute and try again.",
            headers={"Retry-After": str(result.retry_after)},
        )
