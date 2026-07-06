"""Conversations CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import verify_api_key
from src.api.models import ConversationCreate, ConversationOut, ExportOut, MessageFeedback, MessageOut, PinStateOut
from src.persistence import conversation_store, message_repository, message_store, pin_state_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _get_scoped_conversation_or_404(conv_id: str, workspace_id: str | None = None) -> dict:
    conv = conversation_store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    if workspace_id is not None and conv.get("workspace_id", "") != workspace_id:
        raise HTTPException(404, "对话不存在")
    return conv


@router.get("")
async def list_all(workspace_id: str | None = Query(None)) -> list[ConversationOut]:
    conversations = conversation_store.list_conversations(workspace_id=workspace_id)
    return [ConversationOut(**conversation) for conversation in conversations]


@router.post("")
async def create(body: ConversationCreate = ConversationCreate(), workspace_id: str | None = Query(None)) -> ConversationOut:
    conversation = conversation_store.create_conversation(
        body.title,
        workspace_id=workspace_id or "",
    )
    return ConversationOut(**conversation)


@router.get("/{conv_id}")
async def get(conv_id: str, workspace_id: str | None = Query(None)) -> ConversationOut:
    return ConversationOut(**_get_scoped_conversation_or_404(conv_id, workspace_id))


@router.patch("/{conv_id}")
async def update(conv_id: str, body: ConversationCreate, workspace_id: str | None = Query(None)) -> ConversationOut:
    _get_scoped_conversation_or_404(conv_id, workspace_id)
    if not conversation_store.update_title(conv_id, body.title):
        raise HTTPException(404, "对话不存在")
    return ConversationOut(**_get_scoped_conversation_or_404(conv_id, workspace_id))


@router.post("/batch-delete")
async def delete_batch(body: list[str]):
    """批量删除多个对话。"""
    if not body:
        return {"ok": True}
    conversation_store.delete_conversations(body)
    return {"ok": True}


@router.delete("/{conv_id}")
async def delete(conv_id: str, workspace_id: str | None = Query(None)):
    _get_scoped_conversation_or_404(conv_id, workspace_id)
    if not conversation_store.delete_conversation(conv_id):
        raise HTTPException(404, "对话不存在")
    return {"ok": True}


@router.get("/{conv_id}/messages")
async def list_messages(conv_id: str, workspace_id: str | None = Query(None)) -> list[MessageOut]:
    _get_scoped_conversation_or_404(conv_id, workspace_id)
    messages = message_store.get_messages(conv_id)
    return [MessageOut(**message) for message in messages]


@router.get("/{conv_id}/pin-state")
async def get_pin_state(conv_id: str, workspace_id: str | None = Query(None)) -> PinStateOut:
    conv = _get_scoped_conversation_or_404(conv_id, workspace_id)
    summary = pin_state_store.load_pin_state_summary(conv["thread_id"])
    return PinStateOut(**summary)


@router.post("/{conv_id}/messages/{msg_id}/feedback")
async def feedback(conv_id: str, msg_id: int, body: MessageFeedback, workspace_id: str | None = Query(None)):
    _get_scoped_conversation_or_404(conv_id, workspace_id)
    if not message_store.update_feedback(
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
    workspace_id: str | None = Query(None),
) -> ExportOut:
    _get_scoped_conversation_or_404(conv_id, workspace_id)
    result = message_repository.export_conversation(
        conv_id,
        fmt=format,
        include_sources=include_sources,
        include_debug=include_debug,
        get_conversation=conversation_store.get_conversation,
        get_messages_for_conversation=message_store.get_messages,
    )
    if format == "json":
        if not result:
            raise HTTPException(404, "对话不存在")
        return ExportOut(export_json=result)
    if not result:
        raise HTTPException(404, "对话不存在")
    return ExportOut(markdown=result)
