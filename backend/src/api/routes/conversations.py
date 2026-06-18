"""Conversations CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.models import ConversationCreate, ConversationOut, ExportOut, MessageFeedback, MessageOut
from src.conversations import (
    create_conversation, list_conversations, get_conversation, update_title,
    delete_conversation, delete_conversations, get_messages, update_feedback, export_conversation,
)

router = APIRouter()


@router.get("")
async def list_all() -> list[ConversationOut]:
    return [ConversationOut(**c) for c in list_conversations()]


@router.post("")
async def create(body: ConversationCreate = ConversationCreate()) -> ConversationOut:
    return ConversationOut(**create_conversation(body.title))


@router.get("/{conv_id}")
async def get(conv_id: str) -> ConversationOut:
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    return ConversationOut(**conv)


@router.patch("/{conv_id}")
async def update(conv_id: str, body: ConversationCreate) -> ConversationOut:
    update_title(conv_id, body.title)
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
    delete_conversation(conv_id)
    return {"ok": True}


@router.get("/{conv_id}/messages")
async def list_messages(conv_id: str) -> list[MessageOut]:
    return [MessageOut(**m) for m in get_messages(conv_id)]


@router.post("/{conv_id}/messages/{msg_id}/feedback")
async def feedback(conv_id: str, msg_id: int, body: MessageFeedback):
    update_feedback(msg_id, body.feedback)
    return {"ok": True}


@router.get("/{conv_id}/export")
async def export(conv_id: str) -> ExportOut:
    md = export_conversation(conv_id)
    if not md:
        raise HTTPException(404, "对话不存在")
    return ExportOut(markdown=md)
