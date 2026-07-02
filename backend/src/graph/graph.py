"""LangGraph workflow build, caching, and streaming entry points."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import weakref
from functools import partial
from typing import Generator, Iterable

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from src.config.settings import (
    CHECKPOINT_DB_PATH,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_MODEL,
    SCORE_THRESHOLD,
    SILICONFLOW_BASE_URL,
    TOP_K_RETRIEVAL,
    get_runtime_setting,
    require_siliconflow_api_key,
)
from src.graph import nodes as gn
from src.graph.routing import (
    handle_clarification,
    route_after_classifier,
    route_question,
)
from src.graph.state import GraphConfig, GraphState, GraphStateUpdate
from src.rag.knowledge_base import KnowledgeBase


logger = logging.getLogger(__name__)


_GRAPH_CACHE: dict[int, tuple[weakref.ref, object]] = {}
_CHECKPOINTER: SqliteSaver | None = None
_CHECKPOINTER_LOCK = threading.Lock()


def _init_checkpointer():
    global _CHECKPOINTER
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER
    with _CHECKPOINTER_LOCK:
        if _CHECKPOINTER is not None:
            return _CHECKPOINTER
        db_dir = os.path.dirname(CHECKPOINT_DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
        _CHECKPOINTER = SqliteSaver(conn)
        return _CHECKPOINTER


def build_graph(knowledge_base: KnowledgeBase):
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    workflow.add_node("route_question", route_question)
    workflow.add_node("rewrite_query", gn.rewrite_query)
    workflow.add_node("answer_from_history", gn.answer_from_history)
    workflow.add_node("summarize_history", gn.summarize_history)
    workflow.add_node("retrieve_docs", partial(gn.retrieve_docs, kb=knowledge_base))
    workflow.add_node("handle_missing_context", gn.handle_missing_context)
    workflow.add_node("handle_clarification", handle_clarification)
    workflow.add_node("rerank_docs", gn.rerank_docs)
    workflow.add_node("web_search", gn._web_search_context)
    workflow.add_node("generate_answer", gn.generate_answer)
    workflow.add_node("check_quality", gn.check_quality)
    workflow.add_node("finalize", gn.finalize)

    workflow.set_entry_point("route_question")
    workflow.add_conditional_edges(
        "route_question",
        route_after_classifier,
        {
            "rewrite_query": "rewrite_query",
            "answer_from_history": "answer_from_history",
            "summarize_history": "summarize_history",
            "handle_clarification": "handle_clarification",
        },
    )
    workflow.add_edge("rewrite_query", "retrieve_docs")
    workflow.add_conditional_edges(
        "retrieve_docs",
        gn.route_after_retrieval,
        {"rerank_docs": "rerank_docs", "handle_missing_context": "handle_missing_context"},
    )
    workflow.add_edge("rerank_docs", "generate_answer")
    workflow.add_edge("generate_answer", "check_quality")
    workflow.add_edge("answer_from_history", "finalize")
    workflow.add_edge("summarize_history", "finalize")
    workflow.add_edge("handle_clarification", "finalize")
    workflow.add_conditional_edges(
        "handle_missing_context",
        lambda s: "web_search" if not s.get("used_web_search") and s.get("web_search_enabled", False) and gn._tavily_configured() else "finalize",
        {"web_search": "web_search", "finalize": "finalize"},
    )
    workflow.add_edge("web_search", "generate_answer")
    workflow.add_conditional_edges(
        "check_quality",
        gn.should_retry,
        {"web_search": "web_search", "rewrite_query": "rewrite_query", "retrieve_docs": "retrieve_docs", "finalize": "finalize"},
    )
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=_init_checkpointer())


def get_graph(knowledge_base: KnowledgeBase):
    """Return a cached compiled graph for a knowledge base instance."""
    cache_key = id(knowledge_base)
    if cache_key in _GRAPH_CACHE:
        ref, graph = _GRAPH_CACHE[cache_key]
        if ref() is not None:
            return graph
    graph = build_graph(knowledge_base)
    _GRAPH_CACHE[cache_key] = (weakref.ref(knowledge_base), graph)
    return graph


def _initial_state(question: str) -> GraphState:
    return {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "question_type": "knowledge_base",
        "rewritten_question": "",
        "documents": [],
        "context": "",
        "answer": "",
        "sources": [],
        "retry_count": 0,
        "retrieval_k": get_runtime_setting("top_k_retrieval", TOP_K_RETRIEVAL),
        "score_threshold": SCORE_THRESHOLD,
        "quality_ok": True,
        "quality_reason": "",
        "retry_strategy": "none",
        "web_search_results": [],
        "web_context": "",
        "web_search_error": "",
        "used_web_search": False,
        "web_search_enabled": False,
        "search_strategy": "balanced",
        "search_filter": {},
        "pinned_chunk_ids": [],
        "excluded_chunk_ids": [],
        "evidence_level": "none",
        "evidence_summary": "",
        "outcome_category": "success",
        "used_rerank": False,
        "used_rewrite": False,
        "token_count": None,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


def _graph_config(thread_id: str) -> GraphConfig:
    return {"configurable": {"thread_id": thread_id}}


def _state_with_overrides(question: str, **overrides: object) -> GraphState:
    state = _initial_state(question)
    state.update(overrides)
    return state


def _stream_query(question: str, thread_id: str, knowledge_base: KnowledgeBase, **state_overrides: object) -> Iterable[GraphStateUpdate]:
    graph = get_graph(knowledge_base)
    for update in graph.stream(_state_with_overrides(question, **state_overrides), config=_graph_config(thread_id), stream_mode="updates"):
        yield update


def _stream_query_with_tokens(
    question: str, thread_id: str, knowledge_base: KnowledgeBase, **state_overrides: object
) -> Generator[tuple[str, object], None, None]:
    graph = get_graph(knowledge_base)
    for mode, data in graph.stream(
        _state_with_overrides(question, **state_overrides),
        config=_graph_config(thread_id),
        stream_mode=["updates", "messages"],
    ):
        yield (mode, data)


def run_query(
    question: str,
    thread_id: str,
    knowledge_base: KnowledgeBase,
    *,
    stream: bool = False,
    stream_tokens: bool = False,
    web_search_enabled: bool = False,
    search_strategy: str = "balanced",
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> GraphState | Iterable[GraphStateUpdate] | Generator[tuple[str, object], None, None]:
    overrides = {
        "web_search_enabled": web_search_enabled,
        "search_strategy": search_strategy,
    }
    if pinned_chunk_ids:
        overrides["pinned_chunk_ids"] = pinned_chunk_ids
    if excluded_chunk_ids:
        overrides["excluded_chunk_ids"] = excluded_chunk_ids
    if stream_tokens:
        return _stream_query_with_tokens(question, thread_id, knowledge_base, **overrides)
    if stream:
        return _stream_query(question, thread_id, knowledge_base, **overrides)

    graph = get_graph(knowledge_base)
    state = _state_with_overrides(question, **overrides)
    return graph.invoke(state, config=_graph_config(thread_id))
