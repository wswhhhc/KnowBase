"""Admin user management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.auth_tokens import hash_password
from src.api.deps import require_admin
from src.api.models import AdminUserCreate, AdminUserUpdate, UserOut
from src.persistence import auth_store


router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/users")
async def list_users() -> list[UserOut]:
    return [UserOut(**user) for user in auth_store.list_users()]


@router.post("/users")
async def create_user(body: AdminUserCreate) -> UserOut:
    try:
        user = auth_store.create_user(
            username=body.username,
            password_hash=hash_password(body.password),
            role=body.role,
            is_active=body.is_active,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户已存在或数据冲突") from exc
    return UserOut(**user)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: AdminUserUpdate) -> UserOut:
    updates = body.model_dump(exclude_unset=True)
    password = updates.pop("password", None)
    if password is not None:
        updates["password_hash"] = hash_password(password)
    user = auth_store.update_user(user_id, **updates)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return UserOut(**user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str) -> dict:
    if not auth_store.delete_user(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return {"ok": True}
