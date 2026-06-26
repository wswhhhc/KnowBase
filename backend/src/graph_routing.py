"""Question routing and classification for the LangGraph workflow."""

from __future__ import annotations

import json
import logging
import re
from typing import List, Literal

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from config.settings import (
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    SILICONFLOW_BASE_URL,
    require_siliconflow_api_key,
)
from src.graph_state import GraphState, RouteDecision
from src import graph_utils as gu
from src.utils import json_from_text


logger = logging.getLogger(__name__)


_SUMMARY_PATTERNS = (
    r"总结", r"概括", r"回顾", r"梳理",
    r"整理.*(对话|聊天|内容|结论)",
)

_MEMORY_PATTERNS = (
    r"上一次.*(问|说|提到|回答)", r"上一轮.*(问|说|提到|回答)",
    r"刚才.*(问|说|提到|回答)", r"刚刚.*(问|说|提到|回答)",
    r"之前.*(问|说|提到|回答)", r"前面.*(问|说|提到|回答)",
    r"上一句.*(问|说|提到|回答)", r"刚那个.*(问题|内容|回答|说法)",
    r"你知道.*上一次.*吗", r"我刚才.*问.*什么",
    r"我刚刚.*问.*什么", r"你刚才.*说.*什么", r"你刚刚.*说.*什么",
)

_SCOPE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("考勤", "请假", "制度", "规范", "休假", "加班", "报销", "办公"), "local_file"),
    (("飞书", "文档", "手册"), "local_file"),
]


def detect_question_type(question: str, chat_history: List[tuple[str, str]]) -> str:
    """Regex-based question routing (fallback when LLM classifier is unavailable)."""
    normalized = re.sub(r"\s+", "", question.lower())

    if chat_history:
        if any(re.search(pattern, normalized) for pattern in _SUMMARY_PATTERNS):
            return "conversation_summary"
        if any(re.search(pattern, normalized) for pattern in _MEMORY_PATTERNS):
            return "chat_memory"

    return "knowledge_base"


def _route_search_scope(question: str, question_type: str) -> dict:
    """Route to a search filter based on question content and type."""
    if question_type != "knowledge_base":
        return {}
    normalized = re.sub(r"\s+", "", question.lower())
    for keywords, source_type in _SCOPE_RULES:
        if any(kw in normalized for kw in keywords):
            return {"source_type": source_type}
    return {}


def route_question(state: GraphState) -> dict:
    """Classify question: run rules first, LLM only for ambiguous cases."""
    history = gu._messages_to_turns(state.get("messages", []))

    # Rule-based routing first — fast path for obvious cases
    question_type = detect_question_type(state["question"], history)
    if question_type in ("chat_memory", "conversation_summary"):
        search_filter = _route_search_scope(state["question"], question_type)
        return {"question_type": question_type, "search_filter": search_filter}

    # LLM routing for knowledge_base vs clarification ambiguity
    try:
        llm = gu._get_llm()
        history_text = gu._format_chat_history(history, limit=3) if history else "（无历史）"
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是问题分类器。根据用户问题和对话历史，判断意图类型。"
                "只输出 JSON，格式为 {\"question_type\":\"类型\",\"reason\":\"原因\"}。\n\n"
                "类型说明：\n"
                "- knowledge_base：询问知识库内容、技术问题、事实查询。\n"
                "- chat_memory：询问之前的对话内容（如'我刚才问了什么'）。\n"
                "- conversation_summary：要求总结对话（如'总结一下'）。\n"
                "- clarification：问题模糊需要澄清、或纯粹的问候闲聊。",
            ),
            ("human", "对话历史：\n{history}\n\n当前问题：{question}"),
        ])
        result = llm.invoke(
            prompt.format(history=history_text, question=state["question"])
        )
        decision = RouteDecision.model_validate(json_from_text(str(result.content)))
        search_filter = _route_search_scope(state["question"], decision.question_type)
        return {
            "question_type": decision.question_type,
            "search_filter": search_filter,
            **gu.extract_token_usage(result),
        }
    except Exception as exc:
        logger.warning("LLM 路由失败，使用默认路由: %s", exc)

    # LLM failed; default to knowledge_base
    search_filter = _route_search_scope(state["question"], question_type)
    return {"question_type": question_type, "search_filter": search_filter}


def route_after_classifier(
    state: GraphState,
) -> Literal[
    "rewrite_query", "answer_from_history", "summarize_history", "handle_clarification"
]:
    question_type = state.get("question_type", "knowledge_base")
    if question_type == "chat_memory":
        return "answer_from_history"
    if question_type == "conversation_summary":
        return "summarize_history"
    if question_type == "clarification":
        return "handle_clarification"
    return "rewrite_query"


def handle_clarification(state: GraphState) -> dict:
    """Handle ambiguous or greeting-type queries that need human clarification."""
    question = state["question"]
    answer = (
        f"你问的是「{question}」。这个问题比较模糊，能说得更具体一些吗？"
        "你可以补充具体的关键词，或者描述你想了解的主题。"
    )
    return {
        "answer": answer,
        "sources": [],
        "quality_ok": True,
        "quality_reason": "clarification_response",
        "retry_strategy": "none",
        "messages": [AIMessage(content=answer)],
    }
