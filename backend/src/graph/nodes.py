"""Compatibility facade for legacy imports of graph node functions."""

from __future__ import annotations

from src.graph.finalization_nodes import compute_evidence as _compute_evidence, finalize
from src.graph.generation_nodes import generate_answer
from src.graph.history_nodes import answer_from_history, summarize_history
from src.graph.quality_nodes import _rule_check_quality, check_quality, should_retry
from src.graph.retrieval_nodes import (
    _document_relevance_boost,
    _normalize_match_text,
    _query_terms,
    _rewrite_cache,
    _should_rerank,
    handle_missing_context,
    rerank_docs,
    retrieve_docs,
    rewrite_query,
    route_after_rerank,
    route_after_retrieval,
)
from src.graph.web_search_nodes import tavily_configured as _tavily_configured, web_search_context as _web_search_context

__all__ = [
    "_compute_evidence",
    "_document_relevance_boost",
    "_normalize_match_text",
    "_query_terms",
    "_rewrite_cache",
    "_rule_check_quality",
    "_should_rerank",
    "_tavily_configured",
    "_web_search_context",
    "answer_from_history",
    "check_quality",
    "finalize",
    "generate_answer",
    "handle_missing_context",
    "rerank_docs",
    "retrieve_docs",
    "rewrite_query",
    "route_after_rerank",
    "route_after_retrieval",
    "should_retry",
    "summarize_history",
]
