"""Bookmark CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import verify_api_key
from src.persistence import bookmark_store
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
    bookmarks = bookmark_store.list_bookmarks(workspace_id=workspace_id, search=search)
    return [BookmarkOut(**bookmark) for bookmark in bookmarks]


@router.post("")
async def create(body: BookmarkCreate) -> BookmarkOut:
    bookmark = bookmark_store.create_bookmark(**body.model_dump())
    return BookmarkOut(**bookmark)


@router.patch("/{bookmark_id}")
async def update(bookmark_id: int, body: BookmarkUpdate) -> BookmarkOut:
    updated = bookmark_store.update_bookmark(
        bookmark_id,
        **{key: value for key, value in body.model_dump().items() if value is not None},
    )
    if not updated:
        raise HTTPException(404, "书签不存在")
    return BookmarkOut(**updated)


@router.delete("/{bookmark_id}")
async def delete(bookmark_id: int):
    bookmark_store.delete_bookmark(bookmark_id)
    return {"ok": True}
