"""Authentication routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.auth_tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from src.api.deps import get_current_user
from src.api.models import AuthSessionOut, LoginRequest, LogoutRequest, RefreshRequest, UserOut
from src.api.rate_limit import enforce_auth_login_rate_limit
from src.config.settings import settings
from src.persistence import audit_store, auth_store


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


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> AuthSessionOut:
    token_hash = hash_refresh_token(body.refresh_token)
    token = auth_store.get_refresh_token(token_hash)
    if not token or token.get("revoked_at"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if datetime.fromisoformat(token["expires_at"]) <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = auth_store.get_user_by_id(token["user_id"])
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    auth_store.revoke_refresh_token(token_hash)
    return _new_session_for_user(user)


@router.post("/logout")
async def logout(body: LogoutRequest) -> dict:
    auth_store.revoke_refresh_token(hash_refresh_token(body.refresh_token))
    return {"ok": True}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**current_user)
