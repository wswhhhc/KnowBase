"""Utility functions shared across the LangGraph workflow — LLM, context formatting, parsing."""

from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from config.settings import (
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    SILICONFLOW_BASE_URL,
    require_siliconflow_api_key,
)
from src.graph_state import RerankDecision, QualityDecision
from src.kb_models import RetrievalResult
from src.utils import json_from_text


logger = logging.getLogger(__name__)


def _get_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        openai_api_key=require_siliconflow_api_key(),
        openai_api_base=SILICONFLOW_BASE_URL,
    )


def _messages_to_turns(
    messages: List[BaseMessage], exclude_last_human: bool = True
) -> List[tuple[str, str]]:
    """Extract (question, answer) turns from a flat message list."""
    relevant = list(messages)
    if exclude_last_human and relevant and isinstance(relevant[-1], HumanMessage):
        relevant = relevant[:-1]

    turns: list[tuple[str, str]] = []
    pending_question: str | None = None
    for message in relevant:
        if isinstance(message, HumanMessage):
            pending_question = str(message.content)
        elif isinstance(message, AIMessage) and pending_question is not None:
            turns.append((pending_question, str(message.content)))
            pending_question = None
    return turns


def _format_chat_history(
    history: List[tuple[str, str]], limit: int = 6
) -> str:
    """Format recent chat history turns into a prompt string."""
    recent_turns = history[-limit:]
    return "\n".join(
        f"第{i}轮\n用户：{question}\n助手：{answer}"
        for i, (question, answer) in enumerate(recent_turns, 1)
    )


def _format_context(results: list[RetrievalResult]) -> tuple[str, list[dict]]:
    """Format retrieval results into context string and source list."""
    context_parts = []
    sources = []
    for index, result in enumerate(results, 1):
        doc = result.document
        source = doc.metadata.get("source", "未知来源")
        chunk_index = doc.metadata.get("chunk_index", "")
        page = doc.metadata.get("page", "")
        section = doc.metadata.get("section", "")
        loc_parts = [f"来源：{source}"]
        if section:
            loc_parts.append(f"章节：{section}")
        if chunk_index != "":
            loc_parts.append(f"分段：{chunk_index}")
        if page:
            loc_parts.append(f"页码：{page}")
        loc_str = "，".join(loc_parts)
        context_parts.append(
            f"[文档{index}]（ID：{result.chunk_id}，{loc_str}，分数：{result.score:.4f}）\n{doc.page_content}"
        )
        display_content = doc.metadata.get("original_content", doc.page_content)
        sources.append(
            {
                "index": index,
                "chunk_id": result.chunk_id,
                "source": source,
                "chunk_index": chunk_index,
                "page": page,
                "content": display_content[:300],
                "score": result.score,
                "vector_score": result.vector_score,
                "bm25_score": result.bm25_score,
            }
        )
    return "\n\n".join(context_parts), sources


def parse_rerank_decision(text: str, valid_doc_ids: set[str]) -> RerankDecision:
    """Parse and validate a structured rerank decision."""
    try:
        decision = RerankDecision.model_validate(json_from_text(text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return RerankDecision(selected_doc_ids=[])

    return RerankDecision(
        selected_doc_ids=[
            doc_id for doc_id in decision.selected_doc_ids if doc_id in valid_doc_ids
        ],
        reason=decision.reason,
    )


def parse_quality_decision(text: str) -> QualityDecision:
    """Parse a structured quality decision with a conservative fallback."""
    try:
        return QualityDecision.model_validate(json_from_text(text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        normalized = text.strip()
        if normalized.upper().startswith("PASS"):
            return QualityDecision(quality_passed=True, quality_reason="PASS")
        positive_markers = (
            "准确", "正确", "完整", "无错误", "符合事实", "合理", "清晰", "一致", "未编造"
        )
        negative_markers = (
            "不符合", "存在错误", "明显错误", "虚构", "未引用", "无关", "证据不足", "回答过短", "缺失"
        )
        if normalized and any(marker in normalized for marker in positive_markers) and not any(
            marker in normalized for marker in negative_markers
        ):
            return QualityDecision(
                quality_passed=True,
                quality_reason=normalized,
                retry_strategy="none",
            )
        return QualityDecision(
            quality_passed=False,
            quality_reason=normalized or "质量检查未返回有效 JSON。",
            retry_strategy="expand_retrieval",
        )
