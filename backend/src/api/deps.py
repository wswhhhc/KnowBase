"""Dependency injection for FastAPI — shared KnowledgeBase lifecycle."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.auth_tokens import decode_jwt
from src.rag.knowledge_base import KnowledgeBase
from src.config.runtime_overrides import get_runtime_setting
from src.config.settings import settings
from src.persistence import auth_store

_security = HTTPBearer(auto_error=False)
_WORKSPACE_ROLE_RANK = {"viewer": 1, "editor": 2}


def verify_api_key(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> None:
    """Verify Bearer token matches configured API_KEY.

    If no API_KEY is configured, skip auth (local dev mode).
    """
    api_key = get_runtime_setting("api_key", settings.auth.api_key)
    if not api_key:
        return
    if credentials is None or credentials.credentials != api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def _current_user_from_access_token(token: str) -> dict:
    payload = decode_jwt(token, settings.auth.jwt_secret)
    user_id = str(payload.get("sub") or "")
    user = auth_store.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive user")
    return {key: value for key, value in user.items() if key != "password_hash"}


def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_security)]) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _current_user_from_access_token(credentials.credentials)


def get_current_user_or_legacy_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_security)],
) -> dict | None:
    """Return a JWT user, or None for the legacy API-key/local-dev path."""
    api_key = get_runtime_setting("api_key", settings.auth.api_key)
    if credentials is None:
        if not api_key and not settings.is_production:
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if api_key and credentials.credentials == api_key and not settings.is_production:
        return None
    if api_key and credentials.credentials == api_key and settings.is_production:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT login required")
    if api_key and not settings.auth.jwt_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return _current_user_from_access_token(credentials.credentials)


def require_admin(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def require_admin_or_legacy_api_key(
    current_user: Annotated[dict | None, Depends(get_current_user_or_legacy_api_key)],
) -> dict | None:
    if current_user is None:
        return None
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def authorize_workspace_role(current_user: dict | None, workspace_id: str, minimum_role: str) -> dict | None:
    """Require a workspace role for JWT users; allow legacy API-key/local-dev callers."""
    if current_user is None:
        return None
    if current_user.get("role") == "admin":
        return current_user
    user_id = str(current_user.get("id") or "")
    workspace_role = auth_store.get_workspace_member_role(workspace_id=workspace_id, user_id=user_id)
    if workspace_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access required")
    if _WORKSPACE_ROLE_RANK.get(workspace_role, 0) < _WORKSPACE_ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Workspace {minimum_role} role required")
    return current_user


def require_workspace_viewer(
    current_user: Annotated[dict | None, Depends(get_current_user_or_legacy_api_key)],
    workspace_id: str = "",
) -> dict | None:
    return authorize_workspace_role(current_user, workspace_id, "viewer")


def require_workspace_editor(
    current_user: Annotated[dict | None, Depends(get_current_user_or_legacy_api_key)],
    workspace_id: str = "",
) -> dict | None:
    return authorize_workspace_role(current_user, workspace_id, "editor")


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
