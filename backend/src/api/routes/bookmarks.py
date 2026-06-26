"""Bookmark CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import verify_api_key
from src.conversations import (
    create_bookmark, list_bookmarks, delete_bookmark, update_bookmark,
)
from pydantic import BaseModel, Field


class BookmarkOut(BaseModel):
    id: int
    workspace_id: str
    conversation_id: str
    message_id: int
    chunk_id: str
    note: str
    content: str
    source: str
    tags: str = ""
    created_at: str


class BookmarkCreate(BaseModel):
    workspace_id: str = ""
    conversation_id: str = ""
    message_id: int = 0
    chunk_id: str = ""
    note: str = ""
    content: str = ""
    source: str = ""
    tags: str = ""


class BookmarkUpdate(BaseModel):
    note: str | None = None
    tags: str | None = None


router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_all(workspace_id: str | None = Query(None), search: str | None = Query(None)) -> list[BookmarkOut]:
    return [BookmarkOut(**b) for b in list_bookmarks(workspace_id=workspace_id, search=search)]


@router.post("")
async def create(body: BookmarkCreate) -> BookmarkOut:
    return BookmarkOut(**create_bookmark(**body.model_dump()))


@router.patch("/{bookmark_id}")
async def update(bookmark_id: int, body: BookmarkUpdate) -> BookmarkOut:
    updated = update_bookmark(bookmark_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    if not updated:
        raise HTTPException(404, "书签不存在")
    return BookmarkOut(**updated)


@router.delete("/{bookmark_id}")
async def delete(bookmark_id: int):
    delete_bookmark(bookmark_id)
    return {"ok": True}
