"""Persistence helpers for completed chat responses."""

from __future__ import annotations

import json

from src.api.models import DebugInfo
from src.chat_utils import generate_title
from src.persistence import conversation_store, message_store, pin_state_store


def get_conversation_by_thread(thread_id: str) -> dict | None:
    return conversation_store.get_conversation_by_thread(thread_id)


def create_conversation(title: str, *, thread_id: str | None = None, workspace_id: str = "") -> dict:
    return conversation_store.create_conversation(
        title,
        thread_id=thread_id,
        workspace_id=workspace_id,
    )


def replace_pin_state(
    thread_id: str,
    *,
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> None:
    pin_state_store.replace_pin_state(
        thread_id,
        pinned_chunk_ids=pinned_chunk_ids,
        excluded_chunk_ids=excluded_chunk_ids,
    )


def add_message(
    conv_id: str,
    role: str,
    content: str,
    *,
    sources: list | None = None,
    quality_reason: str = "",
    debug_info: str = "{}",
) -> int:
    return message_store.add_message(
        conv_id,
        role,
        content,
        sources=sources,
        quality_reason=quality_reason,
        debug_info=debug_info,
    )


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
    conversation_id = ""
    assistant_message_id = 0

    existing = get_conversation_by_thread(thread_id)
    if existing:
        conversation_id = existing["id"]
    else:
        title = generate_title(question)
        conversation = create_conversation(title, thread_id=thread_id, workspace_id=workspace_id)
        conversation_id = conversation["id"]

    replace_pin_state(
        thread_id,
        pinned_chunk_ids=pinned_chunk_ids,
        excluded_chunk_ids=excluded_chunk_ids,
    )

    add_message(conversation_id, "user", question)
    assistant_message_id = add_message(
        conversation_id,
        "assistant",
        answer,
        sources=final_sources,
        quality_reason=final_quality,
        debug_info=debug_payload,
    )

    return conversation_id, assistant_message_id
