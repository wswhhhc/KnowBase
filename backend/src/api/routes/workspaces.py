"""Workspace CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import require_admin, verify_api_key
from src.api.models import WorkspaceMemberOut, WorkspaceMembersUpdate
from src.persistence import auth_store, workspace_store


class WorkspaceOut(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str


class WorkspaceCreate(BaseModel):
    name: str = "新工作区"
    description: str = ""


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


router = APIRouter()


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_all() -> list[WorkspaceOut]:
    workspaces = workspace_store.list_workspaces()
    return [WorkspaceOut(**workspace) for workspace in workspaces]


@router.post("", dependencies=[Depends(verify_api_key)])
async def create(body: WorkspaceCreate = WorkspaceCreate()) -> WorkspaceOut:
    workspace = workspace_store.create_workspace(body.name, body.description)
    return WorkspaceOut(**workspace)


@router.patch("/{ws_id}", dependencies=[Depends(verify_api_key)])
async def update(ws_id: str, body: WorkspaceUpdate) -> WorkspaceOut:
    if not workspace_store.update_workspace(ws_id, name=body.name, description=body.description):
        raise HTTPException(404, "工作区不存在")
    workspace = workspace_store.get_workspace(ws_id)
    if workspace is None:
        raise HTTPException(500, "更新后未找到工作区")
    return WorkspaceOut(**workspace)


@router.delete("/{ws_id}", dependencies=[Depends(verify_api_key)])
async def delete(ws_id: str):
    if not workspace_store.delete_workspace(ws_id):
        raise HTTPException(404, "工作区不存在")
    return {"ok": True}


@router.get("/{ws_id}/members")
async def list_members(ws_id: str, _admin: dict = Depends(require_admin)) -> list[WorkspaceMemberOut]:
    if workspace_store.get_workspace(ws_id) is None:
        raise HTTPException(404, "工作区不存在")
    members = auth_store.list_workspace_members(ws_id)
    return [WorkspaceMemberOut(**member) for member in members]


@router.put("/{ws_id}/members")
async def replace_members(
    ws_id: str,
    body: WorkspaceMembersUpdate,
    _admin: dict = Depends(require_admin),
) -> list[WorkspaceMemberOut]:
    if workspace_store.get_workspace(ws_id) is None:
        raise HTTPException(404, "工作区不存在")
    user_ids = [member.user_id for member in body.members]
    if len(user_ids) != len(set(user_ids)):
        raise HTTPException(422, "工作区成员不能重复")
    missing_user_ids = [user_id for user_id in user_ids if auth_store.get_user_by_id(user_id) is None]
    if missing_user_ids:
        raise HTTPException(404, "用户不存在")
    members = auth_store.replace_workspace_members(
        workspace_id=ws_id,
        members=[member.model_dump() for member in body.members],
    )
    return [WorkspaceMemberOut(**member) for member in members]
