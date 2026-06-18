"""Chat route — SSE streaming RAG query."""

from __future__ import annotations

import json
import logging
import time
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
        conv_id = None

        # Debug info accumulator
        debug_nodes: list[dict] = []
        debug_rewritten_question = ""
        debug_retrieval_k = 0
        debug_candidates_before = 0
        debug_candidates_after = 0
        debug_after_rerank = 0
        debug_used_rerank = False
        debug_used_rewrite = False
        debug_quality_passed = True
        debug_quality_reason = ""
        debug_retry_count = 0
        debug_used_web_search = False
        debug_web_results_count = 0
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
                            elapsed = int((now - _node_t0) * 1000)
                            _node_t0 = now
                            if node_name == "route_question":
                                qtype = update.get("question_type", "knowledge_base")
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": f"→ {qtype}"})
                            elif node_name == "rewrite_query":
                                rq = update.get("rewritten_question", "")
                                ur = update.get("used_rewrite", False)
                                debug_rewritten_question = rq
                                debug_used_rewrite = bool(ur)
                                summary = f"→ {rq[:40]}" if rq and ur else "无需改写"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "retrieve_docs":
                                srcs = update.get("sources", [])
                                debug_retrieval_k = update.get("retrieval_k", 0) or debug_retrieval_k
                                debug_candidates_before = len(srcs)
                                debug_candidates_after = len(srcs)
                                summary = f"{debug_candidates_before} 候选"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "rerank_docs":
                                ur = update.get("used_rerank", False)
                                debug_used_rerank = bool(ur)
                                srcs = update.get("sources", [])
                                debug_after_rerank = len(srcs)
                                if not ur:
                                    debug_after_rerank = debug_candidates_before
                                summary = f"保留 {debug_after_rerank} 个" if ur else f"跳过 ({debug_candidates_before}→{debug_after_rerank})"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "generate_answer":
                                ans = update.get("answer", "")
                                summary = f"{len(ans)} 字"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "check_quality":
                                qok = update.get("quality_ok", True)
                                debug_quality_passed = bool(qok)
                                qr = update.get("quality_reason", "")
                                debug_quality_reason = qr
                                rc = update.get("retry_count", 0)
                                debug_retry_count = rc if rc else 0
                                strategy = update.get("retry_strategy", "none")
                                summary = "✓ 通过" if qok else f"✗ {qr} (策略:{strategy})"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "web_search":
                                results = update.get("web_search_results", [])
                                debug_web_results_count = len(results)
                                debug_used_web_search = True
                                summary = f"找到 {debug_web_results_count} 条结果"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "handle_missing_context":
                                debug_candidates_before = 0
                                debug_candidates_after = 0
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": "无检索结果"})
                            elif node_name == "handle_clarification":
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": "模糊问题"})
                            elif node_name == "answer_from_history":
                                ans = update.get("answer", "")
                                summary = f"{len(ans)} 字（基于历史）"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "summarize_history":
                                ans = update.get("answer", "")
                                summary = f"{len(ans)} 字（总结历史）"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})
                            elif node_name == "finalize":
                                el = update.get("evidence_level", "")
                                oc = update.get("outcome_category", "")
                                summary = f"证据:{el} 结果:{oc}"
                                debug_nodes.append({"name": node_name, "label": node_label, "elapsed_ms": elapsed, "summary": summary})

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
                nodes=[NodeDebug(**nd) for nd in debug_nodes],
                rewritten_question=debug_rewritten_question,
                retrieval_k=debug_retrieval_k,
                candidates_before=debug_candidates_before,
                candidates_after=debug_candidates_after,
                after_rerank=debug_after_rerank,
                used_rerank=debug_used_rerank,
                used_rewrite=debug_used_rewrite,
                quality_passed=debug_quality_passed,
                quality_reason=debug_quality_reason,
                retry_count=debug_retry_count,
                used_web_search=debug_used_web_search,
                web_results_count=debug_web_results_count,
            )

            # Persist before notifying the client so sidebar refresh sees the final title.
            conv_id = None
            assistant_msg_id = 0
            try:
                existing = get_conversation_by_thread(thread_id)
                if existing:
                    conv_id = existing["id"]
                else:
                    title = generate_title(body.question)
                    conv = create_conversation(title, thread_id=thread_id)
                    conv_id = conv["id"]
                add_message(conv_id, "user", body.question)
                assistant_msg_id = add_message(conv_id, "assistant", answer, sources=final_sources, quality_reason=final_quality, debug_info=debug_info.model_dump_json())
                _record_query_metrics(
                    question=body.question,
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
