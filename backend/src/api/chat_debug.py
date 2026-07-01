"""Debug-state helpers for chat streaming."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DebugState:
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


def accumulate_token_usage(update: dict, debug_state: DebugState) -> None:
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


def accumulate_node_debug(
    node_name: str,
    node_label: str,
    update: dict,
    debug_state: DebugState,
    elapsed_ms: int,
) -> dict | None:
    """Accumulate debug info from a single node update and return a debug-node dict."""
    accumulate_token_usage(update, debug_state)

    if node_name == "route_question":
        qtype = update.get("question_type", "knowledge_base")
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"→ {qtype}"}
    if node_name == "rewrite_query":
        rewritten_question = update.get("rewritten_question", "")
        used_rewrite = update.get("used_rewrite", False)
        debug_state.rewritten_question = rewritten_question
        debug_state.used_rewrite = bool(used_rewrite)
        summary = f"→ {rewritten_question[:40]}" if rewritten_question and used_rewrite else "无需改写"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    if node_name == "retrieve_docs":
        sources = update.get("sources", [])
        debug_state.retrieval_k = update.get("retrieval_k", 0) or debug_state.retrieval_k
        debug_state.candidates_before = len(sources)
        debug_state.candidates_after = len(sources)
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"{debug_state.candidates_before} 候选"}
    if node_name == "rerank_docs":
        used_rerank = update.get("used_rerank", False)
        debug_state.used_rerank = bool(used_rerank)
        sources = update.get("sources", [])
        debug_state.after_rerank = len(sources)
        if not used_rerank:
            debug_state.after_rerank = debug_state.candidates_before
        summary = f"保留 {debug_state.after_rerank} 个" if used_rerank else f"跳过 ({debug_state.candidates_before}→{debug_state.after_rerank})"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    if node_name == "generate_answer":
        answer = update.get("answer", "")
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"{len(answer)} 字"}
    if node_name == "check_quality":
        quality_ok = update.get("quality_ok", True)
        debug_state.quality_passed = bool(quality_ok)
        quality_reason = update.get("quality_reason", "")
        debug_state.quality_reason = quality_reason
        retry_count = update.get("retry_count", 0)
        debug_state.retry_count = retry_count if retry_count else 0
        strategy = update.get("retry_strategy", "none")
        summary = "✓ 通过" if quality_ok else f"✗ {quality_reason} (策略:{strategy})"
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": summary}
    if node_name == "web_search":
        results = update.get("web_search_results", [])
        debug_state.web_results_count = len(results)
        debug_state.used_web_search = True
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"找到 {debug_state.web_results_count} 条结果"}
    if node_name == "handle_missing_context":
        debug_state.candidates_before = 0
        debug_state.candidates_after = 0
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": "无检索结果"}
    if node_name == "handle_clarification":
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": "模糊问题"}
    if node_name == "answer_from_history":
        answer = update.get("answer", "")
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"{len(answer)} 字（基于历史）"}
    if node_name == "summarize_history":
        answer = update.get("answer", "")
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"{len(answer)} 字（总结历史）"}
    if node_name == "finalize":
        evidence_level = update.get("evidence_level", "")
        outcome_category = update.get("outcome_category", "")
        return {"name": node_name, "label": node_label, "elapsed_ms": elapsed_ms, "summary": f"证据:{evidence_level} 结果:{outcome_category}"}
    return None
