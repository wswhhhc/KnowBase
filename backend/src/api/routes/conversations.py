"""Conversations CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import verify_api_key
from src.api.models import ConversationCreate, ConversationOut, ExportOut, MessageFeedback, MessageOut, PinStateOut
from src.persistence import conversation_repository, message_repository, pin_state_repository
from src.persistence.database import get_connection

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_all(workspace_id: str | None = Query(None)) -> list[ConversationOut]:
    conversations = conversation_repository.list_conversations(get_connection, workspace_id=workspace_id)
    return [ConversationOut(**conversation) for conversation in conversations]


@router.post("")
async def create(body: ConversationCreate = ConversationCreate(), workspace_id: str | None = Query(None)) -> ConversationOut:
    conversation = conversation_repository.create_conversation(
        get_connection,
        body.title,
        workspace_id=workspace_id or "",
    )
    return ConversationOut(**conversation)


@router.get("/{conv_id}")
async def get(conv_id: str) -> ConversationOut:
    conv = conversation_repository.get_conversation(get_connection, conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    return ConversationOut(**conv)


@router.patch("/{conv_id}")
async def update(conv_id: str, body: ConversationCreate) -> ConversationOut:
    if not conversation_repository.update_title(get_connection, conv_id, body.title):
        raise HTTPException(404, "对话不存在")
    conv = conversation_repository.get_conversation(get_connection, conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    return ConversationOut(**conv)


@router.post("/batch-delete")
async def delete_batch(body: list[str]):
    """批量删除多个对话。"""
    if not body:
        return {"ok": True}
    conversation_repository.delete_conversations(get_connection, body)
    return {"ok": True}


@router.delete("/{conv_id}")
async def delete(conv_id: str):
    if not conversation_repository.delete_conversation(get_connection, conv_id):
        raise HTTPException(404, "对话不存在")
    return {"ok": True}


@router.get("/{conv_id}/messages")
async def list_messages(conv_id: str) -> list[MessageOut]:
    messages = message_repository.get_messages(get_connection, conv_id)
    return [MessageOut(**message) for message in messages]


@router.get("/{conv_id}/pin-state")
async def get_pin_state(conv_id: str) -> PinStateOut:
    conv = conversation_repository.get_conversation(get_connection, conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    summary = pin_state_repository.load_pin_state_summary(get_connection, conv["thread_id"])
    return PinStateOut(**summary)


@router.post("/{conv_id}/messages/{msg_id}/feedback")
async def feedback(conv_id: str, msg_id: int, body: MessageFeedback):
    if not message_repository.update_feedback(
        get_connection,
        msg_id,
        body.feedback,
        conv_id=conv_id,
        category=body.category,
        detail=body.detail,
    ):
        raise HTTPException(404, "消息不存在")
    return {"ok": True}


@router.get("/{conv_id}/export")
async def export(
    conv_id: str,
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    include_sources: bool = Query(True),
    include_debug: bool = Query(False),
) -> ExportOut:
    result = message_repository.export_conversation(
        conv_id,
        fmt=format,
        include_sources=include_sources,
        include_debug=include_debug,
        get_conversation=lambda target_conv_id: conversation_repository.get_conversation(get_connection, target_conv_id),
        get_messages_for_conversation=lambda target_conv_id: message_repository.get_messages(get_connection, target_conv_id),
    )
    if format == "json":
        if not result:
            raise HTTPException(404, "对话不存在")
        return ExportOut(export_json=result)
    if not result:
        raise HTTPException(404, "对话不存在")
    return ExportOut(markdown=result)
