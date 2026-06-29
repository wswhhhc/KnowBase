"""Chat stream service — extract SSE event generator from the route into a testable class."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from uuid import uuid4

from langchain_core.messages import AIMessageChunk

from src.api.models import ChatRequest, ChatSource, DebugInfo, NodeDebug
from src.chat_utils import NODE_LABELS, record_query_metrics, generate_title
from src.conversations import create_conversation, add_message, get_conversation_by_thread, replace_pin_state
from src.graph import run_query
from src.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


@dataclass
class _DebugState:
    """Mutable accumulator for debug information across graph node updates."""
    nodes: list[dict] = field(default_factory=list)
    rewritten_question: str = ""
    retrieval_k: int = 0
    candidates_before: int = 0
    candidates_after: int = 0
    after_rerank: int = 0
    used_rerank: bool = False
    used_rewrite: bool = False
    quality_passed: bool = True
    quality_reason: str = ""
    retry_count: int = 0
    used_web_search: bool = False
    web_results_count: int = 0
    token_count: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _accumulate_token_usage(update: dict, debug_state: _DebugState) -> None:
    """Sum token usage reported by graph nodes into the per-message debug state."""
    has_usage = any(key in update for key in ("token_count", "prompt_tokens", "completion_tokens"))
    if not has_usage:
        return

    prompt_tokens = int(update.get("prompt_tokens") or 0)
    completion_tokens = int(update.get("completion_tokens") or 0)
    token_count = update.get("token_count")
    if token_count is None:
        token_count = prompt_tokens + completion_tokens

    debug_state.prompt_tokens = (debug_state.prompt_tokens or 0) + prompt_tokens
    debug_state.completion_tokens = (debug_state.completion_tokens or 0) + completion_tokens
    debug_state.token_count = (debug_state.token_count or 0) + int(token_count)


def _accumulate_node_debug(
    node_name: str,
    node_label: str,
    update: dict,
    debug_state: _DebugState,
    elapsed_ms: int,
) -> dict | None:
    """Accumulate debug info from a single node update and return the debug node dict.

    Returns the debug node dict to append to debug_state.nodes, or None if no debug
    entry should be recorded.
    """
    _accumulate_token_usage(update, debug_state)

    if node_name == "route_question":
        qtype = update.get("question_type", "knowledge_base")
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"→ {qtype}"}
    elif node_name == "rewrite_query":
        rq = update.get("rewritten_question", "")
        ur = update.get("used_rewrite", False)
        debug_state.rewritten_question = rq
        debug_state.used_rewrite = bool(ur)
        summary = f"→ {rq[:40]}" if rq and ur else "无需改写"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "retrieve_docs":
        srcs = update.get("sources", [])
        debug_state.retrieval_k = update.get("retrieval_k", 0) or debug_state.retrieval_k
        debug_state.candidates_before = len(srcs)
        debug_state.candidates_after = len(srcs)
        summary = f"{debug_state.candidates_before} 候选"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "rerank_docs":
        ur = update.get("used_rerank", False)
        debug_state.used_rerank = bool(ur)
        srcs = update.get("sources", [])
        debug_state.after_rerank = len(srcs)
        if not ur:
            debug_state.after_rerank = debug_state.candidates_before
        summary = f"保留 {debug_state.after_rerank} 个" if ur else f"跳过 ({debug_state.candidates_before}→{debug_state.after_rerank})"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "generate_answer":
        ans = update.get("answer", "")
        summary = f"{len(ans)} 字"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "check_quality":
        qok = update.get("quality_ok", True)
        debug_state.quality_passed = bool(qok)
        qr = update.get("quality_reason", "")
        debug_state.quality_reason = qr
        rc = update.get("retry_count", 0)
        debug_state.retry_count = rc if rc else 0
        strategy = update.get("retry_strategy", "none")
        summary = "✓ 通过" if qok else f"✗ {qr} (策略:{strategy})"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "web_search":
        results = update.get("web_search_results", [])
        debug_state.web_results_count = len(results)
        debug_state.used_web_search = True
        summary = f"找到 {debug_state.web_results_count} 条结果"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "handle_missing_context":
        debug_state.candidates_before = 0
        debug_state.candidates_after = 0
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": "无检索结果"}
    elif node_name == "handle_clarification":
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": "模糊问题"}
    elif node_name == "answer_from_history":
        ans = update.get("answer", "")
        summary = f"{len(ans)} 字（基于历史）"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "summarize_history":
        ans = update.get("answer", "")
        summary = f"{len(ans)} 字（总结历史）"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    elif node_name == "finalize":
        el = update.get("evidence_level", "")
        oc = update.get("outcome_category", "")
        summary = f"证据:{el} 结果:{oc}"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    return None


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
        self.debug_state = _DebugState()
        self.answer = ""
        self.elapsed = 0
        self.debug_info = DebugInfo()

        # Timing
        self._node_t0 = time.monotonic()
        self.ttfb = 0
        self.first_token = 0
        self._ttfb_set = False

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
                debug_node = _accumulate_node_debug(
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

        # Persist before notifying the client so sidebar refresh sees the final title
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

    # ── Persistence (extracted from former _persist_and_record, 0 params) ─

    def _persist(self) -> tuple[str, int]:
        """Persist conversation and metrics, returning (conv_id, assistant_msg_id)."""
        conv_id = ""
        assistant_msg_id = 0
        try:
            existing = get_conversation_by_thread(self.thread_id)
            if existing:
                conv_id = existing["id"]
            else:
                title = generate_title(self.body.question)
                conv = create_conversation(title, thread_id=self.thread_id, workspace_id=self.body.workspace_id)
                conv_id = conv["id"]

            debug_dict = self.debug_info.model_dump()
            debug_dict["evidence_level"] = self.final_evidence_level
            debug_dict["evidence_summary"] = self.final_evidence_summary
            debug_dict["outcome_category"] = self.final_outcome_category

            replace_pin_state(
                self.thread_id,
                pinned_chunk_ids=self.body.pinned_chunk_ids,
                excluded_chunk_ids=self.body.excluded_chunk_ids,
            )

            add_message(conv_id, "user", self.body.question)
            assistant_msg_id = add_message(
                conv_id, "assistant", self.answer,
                sources=self.final_sources,
                quality_reason=self.final_quality,
                debug_info=json.dumps(debug_dict),
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
        except Exception as exc:
            logger.exception("保存聊天记录或指标失败: %s", exc)
        return conv_id or "", assistant_msg_id
