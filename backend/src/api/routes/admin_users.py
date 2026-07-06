"""Admin user management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.auth_tokens import hash_password
from src.api.deps import require_admin
from src.api.models import AdminUserCreate, AdminUserUpdate, UserOut
from src.persistence import audit_store, auth_store


router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/users")
async def list_users() -> list[UserOut]:
    return [UserOut(**user) for user in auth_store.list_users()]


@router.post("/users")
async def create_user(body: AdminUserCreate, current_user: dict = Depends(require_admin)) -> UserOut:
    try:
        user = auth_store.create_user(
            username=body.username,
            password_hash=hash_password(body.password),
            role=body.role,
            is_active=body.is_active,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户已存在或数据冲突") from exc
    audit_store.record_event(
        action="admin.user_created",
        actor_user_id=current_user.get("id"),
        target_type="user",
        target_id=user["id"],
        metadata={
            "username": user["username"],
            "role": user["role"],
            "is_active": user["is_active"],
        },
    )
    return UserOut(**user)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: AdminUserUpdate, current_user: dict = Depends(require_admin)) -> UserOut:
    updates = body.model_dump(exclude_unset=True)
    password = updates.pop("password", None)
    changed_fields = sorted([*updates.keys(), *(["password"] if password is not None else [])])
    if password is not None:
        updates["password_hash"] = hash_password(password)
    user = auth_store.update_user(user_id, **updates)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    audit_store.record_event(
        action="admin.user_updated",
        actor_user_id=current_user.get("id"),
        target_type="user",
        target_id=user["id"],
        metadata={
            "username": user["username"],
            "changed_fields": changed_fields,
        },
    )
    return UserOut(**user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(require_admin)) -> dict:
    user = auth_store.get_user_by_id(user_id)
    if not auth_store.delete_user(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    audit_store.record_event(
        action="admin.user_deleted",
        actor_user_id=current_user.get("id"),
        target_type="user",
        target_id=user_id,
        metadata={
            "username": user["username"] if user else "",
            "role": user["role"] if user else "",
            "is_active": user["is_active"] if user else False,
        },
    )
    return {"ok": True}
