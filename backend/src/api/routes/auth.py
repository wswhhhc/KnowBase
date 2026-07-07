"""Authentication routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.auth_tokens import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from src.api.deps import get_current_user
from src.api.models import AuthSessionOut, LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, UserOut
from src.api.rate_limit import enforce_auth_login_rate_limit
from src.config.settings import settings
from src.persistence import audit_store, auth_store, workspace_store


router = APIRouter()


def _public_user(user: dict) -> dict:
    return {key: value for key, value in user.items() if key != "password_hash"}


def _new_session_for_user(user: dict) -> AuthSessionOut:
    expires_delta = timedelta(minutes=settings.auth.access_token_minutes)
    access_token = create_access_token(
        user_id=user["id"],
        role=user["role"],
        secret=settings.auth.jwt_secret,
        expires_delta=expires_delta,
    )
    refresh_token = generate_refresh_token()
    auth_store.create_refresh_token(
        user_id=user["id"],
        token_hash=hash_refresh_token(refresh_token),
    )
    return AuthSessionOut(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(expires_delta.total_seconds()),
        user=UserOut(**_public_user(user)),
    )


def _record_refresh_failed(token: dict | None, reason: str) -> None:
    audit_store.record_event(
        action="auth.refresh_failed",
        actor_user_id=token.get("user_id") if token else None,
        target_type="refresh_token" if token else "",
        target_id=token.get("id", "") if token else "",
        metadata={"reason": reason},
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> AuthSessionOut:
    enforce_auth_login_rate_limit(request, body.username)
    user = auth_store.get_user_by_username(body.username)
    if not user or not user.get("is_active") or not verify_password(body.password, user["password_hash"]):
        audit_store.record_event(
            action="auth.login_failed",
            target_type="user",
            target_id=body.username,
            metadata={"username": body.username},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    audit_store.record_event(
        action="auth.login_succeeded",
        actor_user_id=user["id"],
        target_type="user",
        target_id=user["id"],
        metadata={"username": user["username"], "role": user["role"]},
    )
    return _new_session_for_user(user)


@router.post("/register")
async def register(body: RegisterRequest, request: Request) -> AuthSessionOut:
    enforce_auth_login_rate_limit(request, body.username)
    if not settings.auth.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT secret is not configured",
        )
    try:
        user = auth_store.create_user(
            username=body.username,
            password_hash=hash_password(body.password),
            role="editor",
            is_active=True,
        )
        workspace = workspace_store.create_workspace(
            name=f"{user['username']} 的工作区",
            description="自注册账号的个人知识库工作区",
        )
        auth_store.add_workspace_member(workspace_id=workspace["id"], user_id=user["id"], role="editor")
    except Exception as exc:
        audit_store.record_event(
            action="auth.register_failed",
            target_type="user",
            target_id=body.username,
            metadata={"username": body.username, "reason": "duplicate_username"},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户已存在") from exc
    audit_store.record_event(
        action="auth.register_succeeded",
        actor_user_id=user["id"],
        target_type="user",
        target_id=user["id"],
        metadata={
            "username": user["username"],
            "role": user["role"],
            "personal_workspace_id": workspace["id"],
            "personal_workspace_role": "editor",
        },
    )
    return _new_session_for_user(user)


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> AuthSessionOut:
    token_hash = hash_refresh_token(body.refresh_token)
    token = auth_store.get_refresh_token(token_hash)
    if not token or token.get("revoked_at"):
        _record_refresh_failed(token, "revoked_or_unknown")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if datetime.fromisoformat(token["expires_at"]) <= datetime.now(UTC):
        _record_refresh_failed(token, "expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = auth_store.get_user_by_id(token["user_id"])
    if not user or not user.get("is_active"):
        _record_refresh_failed(token, "inactive_user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    auth_store.revoke_refresh_token(token_hash)
    session = _new_session_for_user(user)
    audit_store.record_event(
        action="auth.refresh_succeeded",
        actor_user_id=user["id"],
        target_type="refresh_token",
        target_id=token["id"],
        metadata={"username": user["username"], "role": user["role"]},
    )
    return session


@router.post("/logout")
async def logout(body: LogoutRequest) -> dict:
    token_hash = hash_refresh_token(body.refresh_token)
    token = auth_store.get_refresh_token(token_hash)
    revoked = auth_store.revoke_refresh_token(token_hash)
    if revoked and token:
        audit_store.record_event(
            action="auth.logout_succeeded",
            actor_user_id=token["user_id"],
            target_type="refresh_token",
            target_id=token["id"],
            metadata={},
        )
    return {"ok": True}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**current_user)
