"""Chat route — SSE streaming RAG query."""

from __future__ import annotations

from typing import AsyncGenerator

import anyio
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.api.chat_stream_service import ChatStreamService
from src.api.deps import authorize_workspace_role, get_current_user_or_legacy_api_key, get_knowledge_base
from src.api.models import ChatRequest
from src.api.rate_limit import enforce_chat_stream_rate_limit
from src.persistence import conversation_store
from src.rag.knowledge_base import KnowledgeBase


router = APIRouter()


def _resolve_authorized_workspace_id(body: ChatRequest, current_user: dict | None) -> str:
    if body.thread_id:
        conversation = conversation_store.get_conversation_by_thread(body.thread_id)
        if conversation is not None:
            persisted_workspace_id = str(conversation.get("workspace_id") or "")
            authorize_workspace_role(current_user, persisted_workspace_id, "viewer")
            if persisted_workspace_id != body.workspace_id:
                raise HTTPException(status_code=409, detail="会话与当前工作区不匹配")
            return persisted_workspace_id

    authorize_workspace_role(current_user, body.workspace_id, "viewer")
    return body.workspace_id


@router.post(
    "/stream",
    responses={429: {"description": "请求过于频繁"}},
)
async def chat_stream(
    body: ChatRequest,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
    _rate_limit: None = Depends(enforce_chat_stream_rate_limit),
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    authorized_workspace_id = _resolve_authorized_workspace_id(body, current_user)
    service = ChatStreamService(body, kb, authorized_workspace_id=authorized_workspace_id)

    async def async_wrapper() -> AsyncGenerator[dict, None]:
        sentinel = object()
        iterator = iter(service.run())

        def next_event() -> dict | object:
            try:
                return next(iterator)
            except StopIteration:
                return sentinel

        while True:
            event = await anyio.to_thread.run_sync(next_event)
            if event is sentinel:
                break
            yield event
            await anyio.sleep(0)

    return EventSourceResponse(async_wrapper())
