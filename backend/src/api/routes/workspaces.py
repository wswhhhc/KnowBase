"""Workspace CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key
from pydantic import BaseModel
from src.persistence import workspace_repository
from src.persistence.database import get_connection


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
    workspaces = workspace_repository.list_workspaces(get_connection)
    return [WorkspaceOut(**workspace) for workspace in workspaces]


@router.post("")
async def create(body: WorkspaceCreate = WorkspaceCreate()) -> WorkspaceOut:
    workspace = workspace_repository.create_workspace(get_connection, body.name, body.description)
    return WorkspaceOut(**workspace)


@router.patch("/{ws_id}")
async def update(ws_id: str, body: WorkspaceUpdate) -> WorkspaceOut:
    if not workspace_repository.update_workspace(get_connection, ws_id, name=body.name, description=body.description):
        raise HTTPException(404, "工作区不存在")
    workspace = workspace_repository.get_workspace(get_connection, ws_id)
    if workspace is None:
        raise HTTPException(500, "更新后未找到工作区")
    return WorkspaceOut(**workspace)


@router.delete("/{ws_id}")
async def delete(ws_id: str):
    if not workspace_repository.delete_workspace(get_connection, ws_id):
        raise HTTPException(404, "工作区不存在")
    return {"ok": True}
