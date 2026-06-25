"""Chat route — SSE streaming RAG query."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessageChunk
from sse_starlette.sse import EventSourceResponse

from src.api.deps import get_knowledge_base, verify_api_key
from src.api.models import ChatRequest, DebugInfo, NodeDebug
from src.graph import run_query
from src.knowledge_base import KnowledgeBase
from src.chat_utils import NODE_LABELS, record_query_metrics, generate_title
from src.conversations import create_conversation, add_message, get_conversation_by_thread

router = APIRouter(dependencies=[Depends(verify_api_key)])
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


def _persist_and_record(
    *,
    thread_id: str,
    question: str,
    answer: str,
    conv_id: str | None,
    final_sources: list,
    final_quality: str,
    final_quality_ok: bool,
    final_evidence_level: str,
    final_evidence_summary: str,
    final_outcome_category: str,
    debug_info: DebugInfo,
    elapsed: int,
) -> tuple[str, int]:
    """Persist conversation and metrics, returning (conv_id, assistant_msg_id)."""
    assistant_msg_id = 0
    try:
        existing = get_conversation_by_thread(thread_id)
        if existing:
            conv_id = existing["id"]
        else:
            title = generate_title(question)
            conv = create_conversation(title, thread_id=thread_id)
            conv_id = conv["id"]
        add_message(conv_id, "user", question)
        assistant_msg_id = add_message(conv_id, "assistant", answer, sources=final_sources, quality_reason=final_quality, debug_info=json.dumps({
            **debug_info.model_dump(),
            "evidence_level": final_evidence_level,
            "evidence_summary": final_evidence_summary,
            "outcome_category": final_outcome_category,
        }))
        _record_query_metrics(
            question=question,
            thread_id=thread_id,
            final_sources=final_sources,
            final_quality_ok=final_quality_ok,
            final_quality=final_quality,
            elapsed=elapsed,
            answer=answer,
            debug_info=debug_info,
        )
    except Exception as exc:
        logger.exception("保存聊天记录或指标失败: %s", exc)
    return conv_id or "", assistant_msg_id


def _record_query_metrics(
    *,
    question: str,
    thread_id: str,
    final_sources: list,
    final_quality_ok: bool,
    final_quality: str,
    elapsed: int,
    answer: str,
    debug_info: DebugInfo,
) -> None:
    """Persist the final query metrics using actual debug flags."""
    record_query_metrics(
        question=question,
        thread_id=thread_id,
        final_sources=final_sources,
        final_quality_ok=final_quality_ok,
        final_quality=final_quality,
        elapsed=elapsed,
        answer=answer,
        debug_info=debug_info,
    )


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    thread_id = body.thread_id or str(uuid4())
    t0 = time.monotonic()

    async def event_generator():
        accumulated_answer = ""
        seen_nodes: list[str] = []
        final_sources = []
        final_quality = ""
        final_quality_ok = True
        final_evidence_level = "none"
        final_evidence_summary = ""
        final_outcome_category = "success"

        debug_state = _DebugState()
        # Node timing: track wall-time between SSE update events
        _node_t0 = time.monotonic()

        try:
            events = run_query(
                question=body.question,
                thread_id=thread_id,
                knowledge_base=kb,
                stream_tokens=True,
                web_search_enabled=body.web_search_enabled,
                search_strategy=body.search_strategy,
                pinned_chunk_ids=body.pinned_chunk_ids,
                excluded_chunk_ids=body.excluded_chunk_ids,
            )

            for mode, data in events:
                if mode == "updates":
                    for node_name, update in data.items():
                        node_label = NODE_LABELS.get(node_name, node_name)
                        is_new = node_label not in seen_nodes
                        if is_new:
                            seen_nodes.append(node_label)
                        yield {"event": "node", "data": json.dumps({"label": node_label, "nodes": seen_nodes})}

                        if isinstance(update, dict):
                            accumulated_answer = update.get("answer", accumulated_answer)
                            if update.get("sources"):
                                final_sources = update["sources"]
                            if "quality_ok" in update:
                                final_quality_ok = update["quality_ok"]
                            if update.get("quality_reason"):
                                final_quality = update["quality_reason"]
                            if update.get("evidence_level"):
                                final_evidence_level = update["evidence_level"]
                            if update.get("evidence_summary"):
                                final_evidence_summary = update["evidence_summary"]
                            if update.get("outcome_category"):
                                final_outcome_category = update["outcome_category"]

                            # ---- Debug info accumulation ----
                            now = time.monotonic()
                            elapsed_ms = int((now - _node_t0) * 1000)
                            _node_t0 = now
                            debug_node = _accumulate_node_debug(
                                node_name, node_label, update, debug_state, elapsed_ms,
                            )
                            if debug_node is not None:
                                debug_state.nodes.append(debug_node)

                elif mode == "messages":
                    chunk, metadata = data
                    if (
                        isinstance(chunk, AIMessageChunk)
                        and chunk.content
                        and metadata.get("langgraph_node") == "generate_answer"
                    ):
                        accumulated_answer += chunk.content
                        yield {"event": "token", "data": json.dumps({"text": chunk.content})}

            answer = accumulated_answer.strip() or "抱歉，我无法回答这个问题。"
            elapsed = int((time.monotonic() - t0) * 1000)

            debug_info = DebugInfo(
                nodes=[NodeDebug(**nd) for nd in debug_state.nodes],
                rewritten_question=debug_state.rewritten_question,
                retrieval_k=debug_state.retrieval_k,
                candidates_before=debug_state.candidates_before,
                candidates_after=debug_state.candidates_after,
                after_rerank=debug_state.after_rerank,
                used_rerank=debug_state.used_rerank,
                used_rewrite=debug_state.used_rewrite,
                quality_passed=debug_state.quality_passed,
                quality_reason=debug_state.quality_reason,
                retry_count=debug_state.retry_count,
                used_web_search=debug_state.used_web_search,
                web_results_count=debug_state.web_results_count,
            )

            # Persist before notifying the client so sidebar refresh sees the final title.
            conv_id, assistant_msg_id = _persist_and_record(
                thread_id=thread_id,
                question=body.question,
                answer=answer,
                conv_id=None,
                final_sources=final_sources,
                final_quality=final_quality,
                final_quality_ok=final_quality_ok,
                final_evidence_level=final_evidence_level,
                final_evidence_summary=final_evidence_summary,
                final_outcome_category=final_outcome_category,
                debug_info=debug_info,
                elapsed=elapsed,
            )

            yield {"event": "debug", "data": json.dumps(debug_info.model_dump())}

            yield {"event": "sources", "data": json.dumps({
                "sources": final_sources,
                "quality_reason": final_quality,
                "evidence_level": final_evidence_level,
                "evidence_summary": final_evidence_summary,
                "outcome_category": final_outcome_category,
            })}

            yield {"event": "done", "data": json.dumps({
                "thread_id": thread_id,
                "conv_id": conv_id or "",
                "assistant_msg_id": assistant_msg_id,
                "answer": answer,
                "sources": final_sources,
                "quality_reason": final_quality,
                "evidence_level": final_evidence_level,
                "evidence_summary": final_evidence_summary,
                "outcome_category": final_outcome_category,
                "elapsed_ms": elapsed,
            })}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())
