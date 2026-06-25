"""Bookmark CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import verify_api_key
from src.conversations import (
    create_bookmark, list_bookmarks, delete_bookmark,
)
from pydantic import BaseModel, Field
from datetime import UTC, datetime


class BookmarkOut(BaseModel):
    id: int
    workspace_id: str
    conversation_id: str
    message_id: int
    chunk_id: str
    note: str
    content: str
    source: str
    created_at: str


class BookmarkCreate(BaseModel):
    workspace_id: str = ""
    conversation_id: str = ""
    message_id: int = 0
    chunk_id: str = ""
    note: str = ""
    content: str = ""
    source: str = ""


router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_all(workspace_id: str | None = Query(None)) -> list[BookmarkOut]:
    return [BookmarkOut(**b) for b in list_bookmarks(workspace_id=workspace_id)]


@router.post("")
async def create(body: BookmarkCreate) -> BookmarkOut:
    return BookmarkOut(**create_bookmark(**body.model_dump()))


@router.delete("/{bookmark_id}")
async def delete(bookmark_id: int):
    delete_bookmark(bookmark_id)
    return {"ok": True}
