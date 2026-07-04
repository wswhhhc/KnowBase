"""Simple in-memory rate limiting for critical API routes."""

from __future__ import annotations

import hashlib
import math
import time
from collections import deque
from threading import Lock
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from src.api.deps import _security, verify_api_key
from src.config.runtime_overrides import get_runtime_setting


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


def _resolve_request_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials and credentials.credentials:
        token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()[:16]
        return f"token:{token_hash}"

    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return f"ip:{forwarded_for}"

    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _rate_limit_message(retry_after: int) -> str:
    return f"请求过于频繁，请在 {retry_after} 秒后重试。"


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
        # Preserve the existing auth behavior and return 401 before 429 for bad tokens.
        verify_api_key(credentials)

        limit = int(get_runtime_setting(setting_key, default_limit))
        if limit <= 0:
            return

        limiter: InMemoryRateLimiter = request.app.state.rate_limiter
        identity = _resolve_request_identity(request, credentials)
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

    return _dependency


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
