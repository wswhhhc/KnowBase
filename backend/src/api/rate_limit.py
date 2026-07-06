"""Rate limiting for critical API routes."""

from __future__ import annotations

import hashlib
import math
import time
from uuid import uuid4
from collections import deque
from threading import Lock
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from redis import Redis

from src.api.auth_tokens import decode_jwt
from src.api.deps import _security
from src.config.runtime_overrides import get_runtime_setting
from src.config.settings import settings


class InMemoryRateLimiter:
    """Track request timestamps per bucket using a fixed-size sliding window."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def hit(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> int | None:
        current = time.monotonic() if now is None else now
        cutoff = current - window_seconds

        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (current - bucket[0])))
                return retry_after

            bucket.append(current)
            return None


class RedisRateLimiter:
    """Track request timestamps in Redis with an in-memory fallback for local outages."""

    def __init__(
        self,
        *,
        redis_client=None,
        fallback: InMemoryRateLimiter | None = None,
        key_prefix: str = "knowbase:rate-limit",
    ) -> None:
        self._redis = redis_client or Redis.from_url(
            settings.job_queue.redis_url,
            socket_connect_timeout=0.05,
            socket_timeout=0.05,
        )
        self._fallback = fallback or InMemoryRateLimiter()
        self._key_prefix = key_prefix
        self._redis_disabled_until = 0.0

    def clear(self) -> None:
        self._fallback.clear()
        if self._redis_disabled_until > time.monotonic():
            return
        try:
            keys = list(self._redis.scan_iter(match=f"{self._key_prefix}:*"))
            if keys:
                self._redis.delete(*keys)
        except Exception:
            self._redis_disabled_until = time.monotonic() + 5
            return

    def hit(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> int | None:
        current = time.monotonic() if now is None else now
        redis_key = f"{self._key_prefix}:{key}"
        cutoff = current - window_seconds

        if self._redis_disabled_until > time.monotonic():
            return self._fallback.hit(
                key,
                limit=limit,
                window_seconds=window_seconds,
                now=current,
            )

        try:
            self._redis.zremrangebyscore(redis_key, float("-inf"), cutoff)
            if int(self._redis.zcard(redis_key)) >= limit:
                oldest = self._redis.zrange(redis_key, 0, 0, withscores=True)
                if not oldest:
                    return 1
                oldest_score = float(oldest[0][1])
                return max(1, math.ceil(window_seconds - (current - oldest_score)))

            self._redis.zadd(redis_key, {f"{current:.6f}:{uuid4().hex}": current})
            self._redis.expire(redis_key, max(window_seconds * 2, window_seconds + 1))
            return None
        except Exception:
            self._redis_disabled_until = time.monotonic() + 5
            return self._fallback.hit(
                key,
                limit=limit,
                window_seconds=window_seconds,
                now=current,
            )


def _resolve_request_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return f"ip:{forwarded_for}"

    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _hash_identity(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _resolve_request_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials and credentials.credentials:
        try:
            payload = decode_jwt(credentials.credentials, settings.auth.jwt_secret)
            user_id = str(payload.get("sub") or "").strip()
            if user_id:
                return f"user:{_hash_identity(user_id)}"
        except HTTPException:
            pass

        token_hash = _hash_identity(credentials.credentials)
        return f"token:{token_hash}"

    return _resolve_request_ip(request)


def _rate_limit_message(retry_after: int) -> str:
    return f"请求过于频繁，请在 {retry_after} 秒后重试。"


def enforce_rate_limit(
    request: Request,
    scope: str,
    identity: str,
    *,
    setting_key: str,
    default_limit: int,
    window_seconds: int = 60,
) -> None:
    limit = int(get_runtime_setting(setting_key, default_limit))
    if limit <= 0:
        return

    limiter: InMemoryRateLimiter = request.app.state.rate_limiter
    retry_after = limiter.hit(
        f"{scope}:{identity}",
        limit=limit,
        window_seconds=window_seconds,
    )
    if retry_after is None:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=_rate_limit_message(retry_after),
        headers={"Retry-After": str(retry_after)},
    )


def create_rate_limit_dependency(
    scope: str,
    *,
    setting_key: str,
    default_limit: int,
    window_seconds: int = 60,
) -> Callable[..., None]:
    async def _dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    ) -> None:
        identity = _resolve_request_identity(request, credentials)
        enforce_rate_limit(
            request,
            scope,
            identity,
            setting_key=setting_key,
            default_limit=default_limit,
            window_seconds=window_seconds,
        )

    return _dependency


def enforce_auth_login_rate_limit(request: Request, username: str) -> None:
    normalized_username = username.strip().lower()
    identities = [_resolve_request_ip(request)]
    if normalized_username:
        identities.append(f"user:{_hash_identity(normalized_username)}")
    for identity in identities:
        enforce_rate_limit(
            request,
            "auth-login",
            identity,
            setting_key="auth_login_rate_limit_per_minute",
            default_limit=5,
        )


enforce_chat_stream_rate_limit = create_rate_limit_dependency(
    "chat-stream",
    setting_key="chat_stream_rate_limit_per_minute",
    default_limit=12,
)

enforce_document_import_rate_limit = create_rate_limit_dependency(
    "document-import",
    setting_key="document_import_rate_limit_per_minute",
    default_limit=6,
)
