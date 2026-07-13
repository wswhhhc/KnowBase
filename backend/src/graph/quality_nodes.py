"""Quality-check and retry nodes for the LangGraph workflow."""

from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from src.config.constants import ENABLE_QUALITY_CHECK, MAX_RETRIES, TOP_K_RETRIEVAL
from src.config.runtime_overrides import get_runtime_setting
from src.graph import utils as gu
from src.graph.state import GraphState, GraphStateUpdate, QualityDecision
from src.graph.web_search_nodes import tavily_configured as _tavily_configured


logger = logging.getLogger(__name__)


def _rule_check_quality(state: GraphState) -> GraphStateUpdate | None:
    answer = state.get("answer", "")
    web_context = state.get("web_context", "")
    sources = state.get("sources", [])
    used_web_search = state.get("used_web_search", False)
    documents = state.get("documents", [])

    if not documents and not web_context:
        return {
            "quality_ok": False,
            "quality_reason": "未检索到相关文档。",
            "retry_strategy": "insufficient_context",
        }

    if sources and not any(
        source.get("source") in answer or (source.get("chunk_id") or "") in answer
        for source in sources[:3]
    ):
        pass

    if len(answer.strip()) < 10 and sources:
        return {
            "quality_ok": False,
            "quality_reason": "回答过短。",
            "retry_strategy": "expand_retrieval",
        }

    if used_web_search and sources:
        return {
            "quality_ok": True,
            "quality_reason": "基于网络搜索的回答。",
            "retry_strategy": "none",
        }

    return None


def check_quality(state: GraphState) -> GraphStateUpdate:
    enable_quality_check = get_runtime_setting("enable_quality_check", ENABLE_QUALITY_CHECK)
    if state.get("question_type") != "knowledge_base" or not enable_quality_check:
        answer = state.get("answer", "")
        return {
            "quality_ok": True,
            "quality_reason": "跳过质量检查。",
            "retry_strategy": "none",
            "messages": [AIMessage(content=answer)] if answer else [],
        }

    answer = state.get("answer", "")
    context = state.get("context", "")
    web_context = state.get("web_context", "")
    question = state.get("rewritten_question") or state["question"]
    retry_count = state.get("retry_count", 0)
    used_web_search = state.get("used_web_search", False)
    if web_context:
        context = f"{context}\n\n{web_context}" if context else web_context

    strategy = state.get("search_strategy", "balanced")
    if strategy in ("fast", "balanced") and answer:
        return {
            "quality_ok": True,
            "quality_reason": "标准模式跳过 LLM 质量检查。",
            "retry_strategy": "none",
            "retry_count": retry_count,
            "messages": [AIMessage(content=answer)],
        }

    rule_result = _rule_check_quality(state)
    if rule_result is not None:
        update = {**rule_result, "retry_count": retry_count + 1}
        if rule_result.get("quality_ok") or retry_count + 1 >= MAX_RETRIES:
            update["messages"] = [AIMessage(content=answer)]
            return update
        if not used_web_search and state.get("web_search_enabled", False) and _tavily_configured():
            update["retry_strategy"] = "web_search"
            update["retry_count"] = retry_count
        return update

    token_usage = {}
    llm = gu._get_llm(purpose="auxiliary")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是回答质量审核员。只输出 JSON，格式为 {{\"quality_passed\": true/false, \"quality_reason\": \"原因\", \"retry_strategy\": \"none|rewrite_query|expand_retrieval|insufficient_context\"}}。"),
        ("human", "问题：{question}\n\n参考文档：{context}\n\n回答：{answer}"),
    ])

    try:
        result = llm.invoke(prompt.format(question=question, context=context[:3000], answer=answer))
        decision = gu.parse_quality_decision(str(result.content))
        token_usage = gu.extract_token_usage(result)
    except Exception as exc:
        logger.warning("LLM 质量检查失败，保守放行: %s", exc)
        decision = QualityDecision(quality_passed=True, quality_reason="质量检查调用失败，保守放行。")
        token_usage = {}

    update = {
        "quality_ok": decision.quality_passed,
        "quality_reason": decision.quality_reason,
        "retry_strategy": decision.retry_strategy,
        "retry_count": retry_count + 1,
        **token_usage,
    }
    if decision.quality_passed or retry_count + 1 >= MAX_RETRIES:
        update["messages"] = [AIMessage(content=answer)]
        return update

    if used_web_search:
        update["messages"] = [AIMessage(content=answer)]
        update["retry_strategy"] = "none"
        return update

    if not used_web_search and state.get("web_search_enabled", False) and _tavily_configured():
        update["retry_strategy"] = "web_search"
        update["retry_count"] = retry_count
        return update

    strategy_name = decision.retry_strategy
    if strategy_name == "expand_retrieval":
        default_retrieval_k = get_runtime_setting("top_k_retrieval", TOP_K_RETRIEVAL)
        update["retrieval_k"] = min(
            (state.get("retrieval_k") or default_retrieval_k) + default_retrieval_k,
            default_retrieval_k * 4,
        )
        update["score_threshold"] = None
    elif strategy_name == "rewrite_query":
        update["score_threshold"] = None
    return update


def should_retry(state: GraphState) -> Literal["web_search", "rewrite_query", "retrieve_docs", "finalize"]:
    if state.get("quality_ok", True):
        return "finalize"
    if state.get("retry_strategy") == "web_search":
        return "web_search"
    if state.get("search_strategy") == "deep":
        return "finalize"
    if state.get("retry_count", 0) < MAX_RETRIES:
        retry_strategy = state.get("retry_strategy", "expand_retrieval")
        if retry_strategy == "rewrite_query":
            return "rewrite_query"
        return "retrieve_docs"
    return "finalize"
