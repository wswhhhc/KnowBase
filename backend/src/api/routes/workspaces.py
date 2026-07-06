"""Workspace CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key
from pydantic import BaseModel
from src.persistence import workspace_store


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


router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_all() -> list[WorkspaceOut]:
    workspaces = workspace_store.list_workspaces()
    return [WorkspaceOut(**workspace) for workspace in workspaces]


@router.post("")
async def create(body: WorkspaceCreate = WorkspaceCreate()) -> WorkspaceOut:
    workspace = workspace_store.create_workspace(body.name, body.description)
    return WorkspaceOut(**workspace)


@router.patch("/{ws_id}")
async def update(ws_id: str, body: WorkspaceUpdate) -> WorkspaceOut:
    if not workspace_store.update_workspace(ws_id, name=body.name, description=body.description):
        raise HTTPException(404, "工作区不存在")
    workspace = workspace_store.get_workspace(ws_id)
    if workspace is None:
        raise HTTPException(500, "更新后未找到工作区")
    return WorkspaceOut(**workspace)


@router.delete("/{ws_id}")
async def delete(ws_id: str):
    if not workspace_store.delete_workspace(ws_id):
        raise HTTPException(404, "工作区不存在")
    return {"ok": True}
