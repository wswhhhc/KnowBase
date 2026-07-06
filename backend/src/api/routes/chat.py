"""Chat route — SSE streaming RAG query."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from src.api.chat_stream_service import ChatStreamService
from src.api.deps import authorize_workspace_role, get_current_user_or_legacy_api_key, get_knowledge_base
from src.api.models import ChatRequest
from src.api.rate_limit import enforce_chat_stream_rate_limit
from src.rag.knowledge_base import KnowledgeBase


router = APIRouter()
logger = logging.getLogger(__name__)


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
    authorize_workspace_role(current_user, body.workspace_id, "viewer")
    service = ChatStreamService(body, kb)

    async def async_wrapper() -> AsyncGenerator[dict, None]:
        for event in service.run():
            yield event

    return EventSourceResponse(async_wrapper())
