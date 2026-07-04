"""Web-search helper nodes."""

from __future__ import annotations

from src.config.settings import TAVILY_API_KEY, _is_configured_api_key, get_runtime_setting
from src.graph.state import GraphState, GraphStateUpdate


def web_search_context(state: GraphState) -> GraphStateUpdate:
    from src.rag.web_search import format_search_results, web_search as _web_search

    query = state.get("rewritten_question") or state["question"]
    results, error = _web_search(query, max_results=5)
    web_context = format_search_results(results)
    return {
        "web_search_results": results,
        "web_context": web_context,
        "web_search_error": error,
        "used_web_search": True,
        "quality_reason": (
            f"联网搜索完成：找到 {len(results)} 条结果。"
            if results
            else (error or "联网搜索未返回结果。")
        ),
    }


def tavily_configured() -> bool:
    return _is_configured_api_key(get_runtime_setting("tavily_api_key", TAVILY_API_KEY))
