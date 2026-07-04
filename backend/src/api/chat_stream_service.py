"""Chat stream service — extract SSE event generator from the route into a testable class."""

from __future__ import annotations

import json
import logging
import time
from uuid import uuid4

from langchain_core.messages import AIMessageChunk

from src.api.chat_debug import DebugState, accumulate_node_debug
from src.api.models import ChatRequest, ChatSource, DebugInfo, NodeDebug
from src.api.chat_persistence import build_debug_payload, persist_conversation_turn
from src.chat_utils import NODE_LABELS, record_query_metrics
from src.graph import run_query
from src.persistence import conversation_repository
from src.persistence.database import get_connection
from src.rag.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


def get_conversation_by_thread(thread_id: str) -> dict | None:
    return conversation_repository.get_conversation_by_thread(get_connection, thread_id)


class ChatStreamService:
    """Orchestrates the LangGraph query stream and translates it into SSE events.

    Extracted from the former ``event_generator`` closure so each phase
    (stream, accumulate, persist, emit) is independently understandable
    and testable.
    """

    def __init__(self, body: ChatRequest, kb: KnowledgeBase) -> None:
        self.body = body
        self.kb = kb
        self.thread_id = body.thread_id or str(uuid4())
        self.workspace_id = self._resolve_workspace_id()
        self.t0 = time.monotonic()

        # Accumulators filled during streaming
        self.accumulated_answer = ""
        self.seen_nodes: list[str] = []
        self.final_sources: list = []
        self.final_quality = ""
        self.final_quality_ok = True
        self.final_evidence_level = "none"
        self.final_evidence_summary = ""
        self.final_outcome_category = "success"
        self.debug_state = DebugState()
        self.answer = ""
        self.elapsed = 0
        self.debug_info = DebugInfo()

        # Timing
        self._node_t0 = time.monotonic()
        self.ttfb = 0
        self.first_token = 0
        self._ttfb_set = False

    def _resolve_workspace_id(self) -> str:
        """Use the persisted conversation workspace when a thread already exists."""
        if not self.body.thread_id:
            return self.body.workspace_id

        conversation = get_conversation_by_thread(self.thread_id)
        if not conversation:
            return self.body.workspace_id

        workspace_id = str(conversation.get("workspace_id", ""))
        if workspace_id != self.body.workspace_id:
            logger.info(
                "Chat thread workspace mismatch resolved to persisted scope: thread_id=%s requested=%s persisted=%s",
                self.thread_id,
                self.body.workspace_id,
                workspace_id,
            )
        return workspace_id

    # ── Public entry point ──────────────────────────────────────────────

    def run(self):
        """Generator that yields SSE dicts by streaming through the LangGraph query."""
        try:
            yield from self._stream_updates()
            yield from self._emit_completion()
        except Exception as e:
            logger.exception("Chat stream error")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    # ── Internal phases ─────────────────────────────────────────────────

    def _stream_updates(self):
        """Iterate the LangGraph stream, yielding ``node`` and ``token`` SSE events."""
        events = run_query(
            question=self.body.question,
            thread_id=self.thread_id,
            knowledge_base=self.kb,
            stream_tokens=True,
            web_search_enabled=self.body.web_search_enabled,
            search_strategy=self.body.search_strategy,
            workspace_id=self.workspace_id,
            pinned_chunk_ids=self.body.pinned_chunk_ids,
            excluded_chunk_ids=self.body.excluded_chunk_ids,
        )

        for mode, data in events:
            # TTFB = time from request start until first event of any type
            if not self._ttfb_set:
                self.ttfb = int((time.monotonic() - self.t0) * 1000)
                self._ttfb_set = True

            if mode == "updates":
                yield from self._process_updates(data)
            elif mode == "messages":
                yield from self._process_messages(data)

    def _process_updates(self, data: dict):
        """Handle a LangGraph ``updates`` event: emit node SSE and accumulate state."""
        for node_name, update in data.items():
            node_label = NODE_LABELS.get(node_name, node_name)
            is_new = node_label not in self.seen_nodes
            if is_new:
                self.seen_nodes.append(node_label)
            yield {"event": "node", "data": json.dumps({"label": node_label, "nodes": self.seen_nodes})}

            if isinstance(update, dict):
                self._accumulate_update(update)

                now = time.monotonic()
                elapsed_ms = int((now - self._node_t0) * 1000)
                self._node_t0 = now
                debug_node = accumulate_node_debug(
                    node_name, node_label, update, self.debug_state, elapsed_ms,
                )
                if debug_node is not None:
                    self.debug_state.nodes.append(debug_node)

    def _process_messages(self, data):
        """Handle a LangGraph ``messages`` event: emit token SSE for ``generate_answer``."""
        chunk, metadata = data
        if (
            isinstance(chunk, AIMessageChunk)
            and chunk.content
            and metadata.get("langgraph_node") == "generate_answer"
        ):
            if self.first_token == 0:
                self.first_token = int((time.monotonic() - self.t0) * 1000)
            self.accumulated_answer += chunk.content
            yield {"event": "token", "data": json.dumps({"text": chunk.content})}

    def _accumulate_update(self, update: dict) -> None:
        """Merge state from a graph node update into the service accumulators."""
        self.accumulated_answer = update.get("answer", self.accumulated_answer)
        if update.get("sources"):
            self.final_sources = update["sources"]
        if "quality_ok" in update:
            self.final_quality_ok = update["quality_ok"]
        if update.get("quality_reason"):
            self.final_quality = update["quality_reason"]
        if update.get("evidence_level"):
            self.final_evidence_level = update["evidence_level"]
        if update.get("evidence_summary"):
            self.final_evidence_summary = update["evidence_summary"]
        if update.get("outcome_category"):
            self.final_outcome_category = update["outcome_category"]

    def _emit_completion(self):
        """Build debug info, persist, then yield ``debug``, ``sources``, and ``done`` events."""
        self.answer = self.accumulated_answer.strip() or "抱歉，我无法回答这个问题。"
        self.elapsed = int((time.monotonic() - self.t0) * 1000)

        self.debug_info = DebugInfo(
            nodes=[NodeDebug(**nd) for nd in self.debug_state.nodes],
            rewritten_question=self.debug_state.rewritten_question,
            retrieval_k=self.debug_state.retrieval_k,
            candidates_before=self.debug_state.candidates_before,
            candidates_after=self.debug_state.candidates_after,
            after_rerank=self.debug_state.after_rerank,
            used_rerank=self.debug_state.used_rerank,
            used_rewrite=self.debug_state.used_rewrite,
            quality_passed=self.debug_state.quality_passed,
            quality_reason=self.debug_state.quality_reason,
            retry_count=self.debug_state.retry_count,
            used_web_search=self.debug_state.used_web_search,
            web_results_count=self.debug_state.web_results_count,
            context_sources=[ChatSource.model_validate(source) for source in self.final_sources if isinstance(source, dict)],
            token_count=self.debug_state.token_count,
            prompt_tokens=self.debug_state.prompt_tokens,
            completion_tokens=self.debug_state.completion_tokens,
        )

        conv_id, assistant_msg_id = self._persist()

        yield {"event": "debug", "data": json.dumps(self.debug_info.model_dump())}

        yield {"event": "sources", "data": json.dumps({
            "sources": self.final_sources,
            "quality_reason": self.final_quality,
            "evidence_level": self.final_evidence_level,
            "evidence_summary": self.final_evidence_summary,
            "outcome_category": self.final_outcome_category,
        })}

        yield {"event": "done", "data": json.dumps({
            "thread_id": self.thread_id,
            "conv_id": conv_id or "",
            "assistant_msg_id": assistant_msg_id,
            "answer": self.answer,
            "sources": self.final_sources,
            "quality_reason": self.final_quality,
            "evidence_level": self.final_evidence_level,
            "evidence_summary": self.final_evidence_summary,
            "outcome_category": self.final_outcome_category,
            "elapsed_ms": self.elapsed,
        })}

    def _persist(self) -> tuple[str, int]:
        """Persist conversation state from instance fields and record query metrics."""
        try:
            debug_payload = build_debug_payload(
                self.debug_info,
                evidence_level=self.final_evidence_level,
                evidence_summary=self.final_evidence_summary,
                outcome_category=self.final_outcome_category,
                search_strategy=self.body.search_strategy,
            )
            conversation_id, assistant_message_id = persist_conversation_turn(
                question=self.body.question,
                thread_id=self.thread_id,
                workspace_id=self.workspace_id,
                answer=self.answer,
                final_sources=self.final_sources,
                final_quality=self.final_quality,
                debug_payload=debug_payload,
                pinned_chunk_ids=self.body.pinned_chunk_ids,
                excluded_chunk_ids=self.body.excluded_chunk_ids,
            )
            record_query_metrics(
                question=self.body.question,
                thread_id=self.thread_id,
                final_sources=self.final_sources,
                final_quality_ok=self.final_quality_ok,
                final_quality=self.final_quality,
                elapsed=self.elapsed,
                answer=self.answer,
                debug_info=self.debug_info,
                ttfb_ms=self.ttfb,
                first_token_ms=self.first_token,
                token_count=self.debug_info.token_count,
                prompt_tokens=self.debug_info.prompt_tokens if self.debug_info.prompt_tokens is not None else self.debug_state.prompt_tokens,
                completion_tokens=self.debug_info.completion_tokens if self.debug_info.completion_tokens is not None else self.debug_state.completion_tokens,
            )
            return conversation_id, assistant_message_id
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("保存聊天记录或指标失败: %s", exc)
            return "", 0
