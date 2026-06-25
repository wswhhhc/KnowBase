"""Workspace CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key
from src.conversations import (
    create_workspace, list_workspaces, update_workspace, delete_workspace,
)
from pydantic import BaseModel


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
    return [WorkspaceOut(**w) for w in list_workspaces()]


@router.post("")
async def create(body: WorkspaceCreate = WorkspaceCreate()) -> WorkspaceOut:
    return WorkspaceOut(**create_workspace(body.name, body.description))


@router.patch("/{ws_id}")
async def update(ws_id: str, body: WorkspaceUpdate) -> WorkspaceOut:
    if not update_workspace(ws_id, name=body.name, description=body.description):
        raise HTTPException(404, "工作区不存在")
    from src.conversations import get_conversation
    return WorkspaceOut(id=ws_id, name=body.name or "", description=body.description or "", created_at="", updated_at="")


@router.delete("/{ws_id}")
async def delete(ws_id: str):
    if not delete_workspace(ws_id):
        raise HTTPException(404, "工作区不存在")
    return {"ok": True}
