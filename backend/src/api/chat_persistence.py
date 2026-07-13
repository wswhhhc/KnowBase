"""Persistence helpers for completed chat responses."""

from __future__ import annotations

import json

from src.api.models import DebugInfo
from src.chat_utils import generate_title
from src.persistence import conversation_store
from src.persistence.conversation_repository import ConversationWorkspaceMismatchError


def build_debug_payload(
    debug_info: DebugInfo,
    *,
    evidence_level: str,
    evidence_summary: str,
    outcome_category: str,
    search_strategy: str,
) -> str:
    """Serialize the debug payload stored with assistant messages."""
    payload = debug_info.model_dump()
    payload["evidence_level"] = evidence_level
    payload["evidence_summary"] = evidence_summary
    payload["outcome_category"] = outcome_category
    payload["search_strategy"] = search_strategy
    return json.dumps(payload)


def persist_conversation_turn(
    *,
    question: str,
    thread_id: str,
    workspace_id: str,
    answer: str,
    final_sources: list,
    final_quality: str,
    debug_payload: str,
    pinned_chunk_ids: list[str],
    excluded_chunk_ids: list[str],
) -> tuple[str, int]:
    """Persist the conversation turn and return (conversation_id, assistant_message_id)."""
    existing = conversation_store.get_conversation_by_thread(thread_id)
    if existing:
        existing_workspace_id = str(existing.get("workspace_id") or "")
        if existing_workspace_id != workspace_id:
            raise ConversationWorkspaceMismatchError("会话与当前工作区不匹配")
        title = question[:30]
    else:
        title = generate_title(question)

    return conversation_store.persist_conversation_turn(
        title=title,
        question=question,
        thread_id=thread_id,
        workspace_id=workspace_id,
        answer=answer,
        final_sources=final_sources,
        final_quality=final_quality,
        debug_payload=debug_payload,
        pinned_chunk_ids=pinned_chunk_ids,
        excluded_chunk_ids=excluded_chunk_ids,
    )
