"""Bookmark CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import authorize_workspace_role, get_current_user_or_legacy_api_key
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


router = APIRouter()


def _workspace_scope_for_list(workspace_id: str | None, current_user: dict | None) -> str | None:
    if workspace_id is not None:
        return workspace_id
    return "" if current_user is not None else None


def _authorize_workspace(current_user: dict | None, workspace_id: str, role: str) -> None:
    authorize_workspace_role(current_user, workspace_id, role)


def _get_bookmark_or_404(bookmark_id: int) -> dict:
    bookmark = bookmark_store.get_bookmark(bookmark_id)
    if bookmark is None:
        raise HTTPException(404, "书签不存在")
    return bookmark


@router.get("")
async def list_all(
    workspace_id: str | None = Query(None),
    search: str | None = Query(None),
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> list[BookmarkOut]:
    scoped_workspace_id = _workspace_scope_for_list(workspace_id, current_user)
    if current_user is not None:
        _authorize_workspace(current_user, scoped_workspace_id or "", "viewer")
    bookmarks = bookmark_store.list_bookmarks(workspace_id=scoped_workspace_id, search=search)
    return [BookmarkOut(**bookmark) for bookmark in bookmarks]


@router.post("")
async def create(
    body: BookmarkCreate,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> BookmarkOut:
    if current_user is not None:
        _authorize_workspace(current_user, body.workspace_id, "editor")
    bookmark = bookmark_store.create_bookmark(**body.model_dump())
    return BookmarkOut(**bookmark)


@router.patch("/{bookmark_id}")
async def update(
    bookmark_id: int,
    body: BookmarkUpdate,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> BookmarkOut:
    bookmark = _get_bookmark_or_404(bookmark_id)
    if current_user is not None:
        _authorize_workspace(current_user, bookmark["workspace_id"], "editor")
    updated = bookmark_store.update_bookmark(
        bookmark_id,
        **{key: value for key, value in body.model_dump().items() if value is not None},
    )
    if not updated:
        raise HTTPException(404, "书签不存在")
    return BookmarkOut(**updated)


@router.delete("/{bookmark_id}")
async def delete(
    bookmark_id: int,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
):
    bookmark = bookmark_store.get_bookmark(bookmark_id)
    if current_user is not None:
        if bookmark is None:
            raise HTTPException(404, "书签不存在")
        _authorize_workspace(current_user, bookmark["workspace_id"], "editor")
    bookmark_store.delete_bookmark(bookmark_id)
    return {"ok": True}
