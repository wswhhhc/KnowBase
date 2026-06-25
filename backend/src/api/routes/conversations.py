"""Conversations CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import verify_api_key
from src.api.models import ConversationCreate, ConversationOut, ExportOut, MessageFeedback, MessageOut
from src.conversations import (
    create_conversation, list_conversations, get_conversation, update_title,
    delete_conversation, delete_conversations, get_messages, update_feedback, export_conversation,
    create_workspace, list_workspaces, update_workspace, delete_workspace,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_all(workspace_id: str | None = Query(None)) -> list[ConversationOut]:
    return [ConversationOut(**c) for c in list_conversations(workspace_id=workspace_id)]


@router.post("")
async def create(body: ConversationCreate = ConversationCreate(), workspace_id: str | None = Query(None)) -> ConversationOut:
    return ConversationOut(**create_conversation(body.title, workspace_id=workspace_id or ""))


@router.get("/{conv_id}")
async def get(conv_id: str) -> ConversationOut:
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    return ConversationOut(**conv)


@router.patch("/{conv_id}")
async def update(conv_id: str, body: ConversationCreate) -> ConversationOut:
    if not update_title(conv_id, body.title):
        raise HTTPException(404, "对话不存在")
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    return ConversationOut(**conv)


@router.post("/batch-delete")
async def delete_batch(body: list[str]):
    """批量删除多个对话。"""
    if not body:
        return {"ok": True}
    delete_conversations(body)
    return {"ok": True}


@router.delete("/{conv_id}")
async def delete(conv_id: str):
    if not delete_conversation(conv_id):
        raise HTTPException(404, "对话不存在")
    return {"ok": True}


@router.get("/{conv_id}/messages")
async def list_messages(conv_id: str) -> list[MessageOut]:
    return [MessageOut(**m) for m in get_messages(conv_id)]


@router.post("/{conv_id}/messages/{msg_id}/feedback")
async def feedback(conv_id: str, msg_id: int, body: MessageFeedback):
    if not update_feedback(msg_id, body.feedback, conv_id=conv_id, category=body.category, detail=body.detail):
        raise HTTPException(404, "消息不存在")
    return {"ok": True}


@router.get("/{conv_id}/export")
async def export(
    conv_id: str,
    format: str = Query("markdown", regex="^(markdown|json)$"),
    include_sources: bool = Query(True),
    include_debug: bool = Query(False),
) -> ExportOut:
    result = export_conversation(conv_id, fmt=format, include_sources=include_sources, include_debug=include_debug)
    if format == "json":
        if not result:
            raise HTTPException(404, "对话不存在")
        return ExportOut(json=result)
    if not result:
        raise HTTPException(404, "对话不存在")
    return ExportOut(markdown=result)
