"""Dependency injection for FastAPI — shared KnowledgeBase lifecycle."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.knowledge_base import KnowledgeBase
from config.settings import settings

_security = HTTPBearer(auto_error=False)


def verify_api_key(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> None:
    """Verify Bearer token matches configured API_KEY.

    If no API_KEY is configured, skip auth (local dev mode).
    """
    if not settings.api_key:
        return
    if credentials is None or credentials.credentials != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    """Return the singleton KnowledgeBase (initialized on first call)."""
    try:
        return KnowledgeBase()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
