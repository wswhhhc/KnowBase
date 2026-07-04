"""Finalization and evidence summary nodes."""

from __future__ import annotations

from src.graph.state import GraphState, GraphStateUpdate


def compute_evidence(state: GraphState) -> tuple[str, str, str]:
    sources = state.get("sources", [])
    used_web = state.get("used_web_search", False)
    quality_ok = state.get("quality_ok", True)
    quality_reason = state.get("quality_reason", "")
    question_type = state.get("question_type", "knowledge_base")

    local_count = sum(1 for source in sources if not source.get("url"))
    web_count = sum(1 for source in sources if source.get("url"))

    if question_type == "clarification":
        return "none", "vague_question", "问题描述比较模糊，建议补充具体信息"
    if question_type in ("chat_memory", "conversation_summary"):
        return "strong", "success", "基于对话历史回答"

    if not local_count and not used_web:
        return "none", "no_docs", "工作区中没有找到相关内容"
    if not local_count and used_web and not web_count:
        return "none", "web_empty", "工作区和联网搜索都没有找到相关内容"

    if quality_ok and local_count >= 2:
        parts = [f"基于 {local_count} 个本地文档片段"]
        if web_count:
            parts.append(f"联网补充 {web_count} 条")
        return "strong", "success", "，".join(parts)
    if quality_ok and local_count == 1:
        parts = [f"基于 {local_count} 个本地文档片段"]
        if web_count:
            parts.append(f"联网补充 {web_count} 条")
        return "moderate", "success", "，".join(parts)

    if quality_reason and "未检索" in quality_reason:
        return "none", "no_docs", "工作区中没有找到相关内容"
    if used_web and not web_count:
        return "none", "web_empty", "工作区和联网搜索都没有找到足够相关的内容"
    return "weak", "weak_evidence", f"检索到 {local_count} 个相关片段，但证据不够充分"


def finalize(state: GraphState) -> GraphStateUpdate:
    evidence_level, outcome_category, evidence_summary = compute_evidence(state)
    return {
        "evidence_level": evidence_level,
        "outcome_category": outcome_category,
        "evidence_summary": evidence_summary,
    }
