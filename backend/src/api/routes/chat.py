"""Chat route — SSE streaming RAG query."""

from __future__ import annotations

import json
import time
from uuid import uuid4

from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessageChunk
from sse_starlette.sse import EventSourceResponse

from src.api.deps import get_knowledge_base
from src.api.models import ChatRequest
from src.graph import run_query
from src.knowledge_base import KnowledgeBase
from src.metrics import log_query
from src.conversations import create_conversation, add_message, get_conversation_by_thread

router = APIRouter()

NODE_LABELS = {
    "route_question": "问题路由",
    "rewrite_query": "查询改写",
    "retrieve_docs": "混合检索",
    "rerank_docs": "结构化重排",
    "generate_answer": "生成回答",
    "check_quality": "质量检查",
    "web_search": "联网搜索",
    "answer_from_history": "会话记忆",
    "summarize_history": "会话总结",
    "handle_missing_context": "证据不足兜底",
    "handle_clarification": "模糊问题提示",
}


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    thread_id = body.thread_id or str(uuid4())
    t0 = time.monotonic()

    async def event_generator():
        accumulated_answer = ""
        seen_nodes: set[str] = set()
        final_sources = []
        final_quality = ""
        final_quality_ok = True
        final_evidence_level = "none"
        final_evidence_summary = ""
        final_outcome_category = "success"
        conv_id = None

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
                        if node_label not in seen_nodes:
                            seen_nodes.add(node_label)
                        yield {"event": "node", "data": json.dumps({"label": node_label, "nodes": list(seen_nodes)})}

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

            yield {"event": "sources", "data": json.dumps({
                "sources": final_sources,
                "quality_reason": final_quality,
                "evidence_level": final_evidence_level,
                "evidence_summary": final_evidence_summary,
                "outcome_category": final_outcome_category,
            })}

            yield {"event": "done", "data": json.dumps({
                "thread_id": thread_id,
                "answer": answer,
                "sources": final_sources,
                "quality_reason": final_quality,
                "evidence_level": final_evidence_level,
                "evidence_summary": final_evidence_summary,
                "outcome_category": final_outcome_category,
                "elapsed_ms": elapsed,
            })}

            # Fire-and-forget persist
            try:
                existing = get_conversation_by_thread(thread_id)
                if existing:
                    conv_id = existing["id"]
                else:
                    title = body.question[:30]
                    conv = create_conversation(title)
                    conv_id = conv["id"]
                add_message(conv_id, "user", body.question)
                add_message(conv_id, "assistant", answer, sources=final_sources, quality_reason=final_quality)
                log_query(
                    question=body.question, thread_id=thread_id, question_type="knowledge_base",
                    retrieval_count=len(final_sources), retry_count=0, quality_ok=final_quality_ok,
                    quality_reason=final_quality, source_count=len(final_sources), elapsed_ms=elapsed,
                    answer=answer, used_web_search=bool(final_sources), used_rerank=None,
                )
            except Exception:
                pass

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())
