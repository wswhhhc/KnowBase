"""Chat route — SSE streaming RAG query."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from src.api.chat_stream_service import ChatStreamService
from src.api.deps import get_knowledge_base, verify_api_key
from src.api.models import ChatRequest
from src.knowledge_base import KnowledgeBase


router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    service = ChatStreamService(body, kb)

    async def async_wrapper() -> AsyncGenerator[dict, None]:
        for event in service.run():
            yield event

    return EventSourceResponse(async_wrapper())
