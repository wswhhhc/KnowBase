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
from src.config.settings import settings
from src.graph import run_query
from src.rag.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

ANSWER_STREAM_NODES = {"generate_answer", "answer_from_history", "summarize_history"}

class ChatStreamService:
    """Orchestrates the LangGraph query stream and translates it into SSE events.

    Extracted from the former ``event_generator`` closure so each phase
    (stream, accumulate, persist, emit) is independently understandable
    and testable.
    """

    def __init__(
        self,
        body: ChatRequest,
        kb: KnowledgeBase,
        *,
        authorized_workspace_id: str,
    ) -> None:
        self.body = body
        self.kb = kb
        self.thread_id = body.thread_id or str(uuid4())
        self.workspace_id = authorized_workspace_id
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
        self._manual_token_streamed = False
        self._stream_error: Exception | None = None

    # ── Public entry point ──────────────────────────────────────────────

    def run(self):
        """Generator that yields SSE dicts by streaming through the LangGraph query."""
        try:
            if settings.e2e_fake_ai:
                yield from self._run_e2e_fake_chat()
                return
            self._refresh_kb_before_graph_read()
            yield from self._stream_updates()
            yield from self._emit_completion()
        except Exception as e:
            logger.exception("Chat stream error")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    def _refresh_kb_before_graph_read(self) -> None:
        refresh = getattr(self.kb, "refresh_from_persisted_store", None)
        if callable(refresh):
            refresh()

    # ── Internal phases ─────────────────────────────────────────────────

    def _stream_updates(self):
        """Iterate the LangGraph stream, yielding ``node`` and ``token`` SSE events."""
        pending_token_events: list[dict] = []

        def enqueue_token(text: str) -> None:
            if not text:
                return
            if self.first_token == 0:
                self.first_token = int((time.monotonic() - self.t0) * 1000)
            self._manual_token_streamed = True
            self.accumulated_answer += text
            pending_token_events.append({"event": "token", "data": json.dumps({"text": text})})

        def drain_pending_tokens():
            while pending_token_events:
                yield pending_token_events.pop(0)

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
            token_callback=enqueue_token,
        )

        for mode, data in events:
            # TTFB = time from request start until first event of any type
            if not self._ttfb_set:
                self.ttfb = int((time.monotonic() - self.t0) * 1000)
                self._ttfb_set = True
            yield from drain_pending_tokens()

            if mode == "updates":
                yield from self._process_updates(data)
            elif mode == "messages":
                yield from self._process_messages(data)
            yield from drain_pending_tokens()

        yield from drain_pending_tokens()

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
            and metadata.get("langgraph_node") in ANSWER_STREAM_NODES
        ):
            if self._manual_token_streamed:
                return
            if self.first_token == 0:
                self.first_token = int((time.monotonic() - self.t0) * 1000)
            self.accumulated_answer += chunk.content
            yield {"event": "token", "data": json.dumps({"text": chunk.content})}

    def _run_e2e_fake_chat(self):
        """Deterministic chat path for Playwright E2E without external model calls."""
        yield {"event": "node", "data": json.dumps({"label": "检索知识库", "nodes": ["检索知识库"]})}

        chunks = self._list_e2e_fake_chunks()
        sources = []
        if chunks:
            chunk = chunks[0]
            content = chunk.original_content or chunk.content
            sources = [{
                "source": chunk.source,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "page": chunk.page,
                "score": 1.0,
                "content": content,
                "index": 1,
            }]
            snippet = content.replace("\n", " ").strip()[:120]
            self.accumulated_answer = f"已根据当前工作区资料回答：{snippet} [1]"
            self.final_evidence_level = "high"
            self.final_evidence_summary = "E2E fake chat used one imported workspace chunk."
            self.final_outcome_category = "success"
        else:
            self.accumulated_answer = "当前工作区还没有可用于回答的资料。"
            self.final_evidence_level = "none"
            self.final_outcome_category = "no_evidence"

        self.final_sources = sources
        self.final_quality = "E2E fake chat"
        self.final_quality_ok = bool(sources)
        self.debug_state.retrieval_k = len(sources)
        self.debug_state.candidates_before = len(sources)
        self.debug_state.candidates_after = len(sources)
        self.debug_state.quality_passed = bool(sources)
        self.debug_state.quality_reason = self.final_quality

        for token in self.accumulated_answer:
            if self.first_token == 0:
                self.first_token = int((time.monotonic() - self.t0) * 1000)
            yield {"event": "token", "data": json.dumps({"text": token})}

        yield from self._emit_completion()

    def _list_e2e_fake_chunks(self):
        _total, chunks = self.kb.list_chunks(workspace_id=self.workspace_id, limit=1)
        if chunks or not isinstance(self.kb, KnowledgeBase):
            return chunks

        # E2E imports run in the worker process, while the API process may
        # still hold a cached KnowledgeBase created before the import. Reopen
        # Chroma without embeddings so the fake chat path sees persisted rows.
        fresh_kb = KnowledgeBase(require_embeddings=False)
        _fresh_total, fresh_chunks = fresh_kb.list_chunks(workspace_id=self.workspace_id, limit=1)
        return fresh_chunks

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
