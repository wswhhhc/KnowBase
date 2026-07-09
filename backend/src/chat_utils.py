"""Chat route helpers — title generation, metrics recording, node labels."""

from __future__ import annotations

import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.constants import LLM_MODEL, SILICONFLOW_BASE_URL
from src.config.runtime_overrides import _is_configured_api_key, get_runtime_setting, require_siliconflow_api_key
from src.api.models import DebugInfo
from src.metrics import log_query

logger = logging.getLogger(__name__)

_AUXILIARY_LLM_TIMEOUT_SECONDS = 15


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


def _create_auxiliary_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=get_runtime_setting("llm_model", LLM_MODEL),
        temperature=0.3,
        openai_api_key=require_siliconflow_api_key(),
        openai_api_base=get_runtime_setting("siliconflow_base_url", SILICONFLOW_BASE_URL),
        timeout=_AUXILIARY_LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )


def record_query_metrics(
    *,
    question: str,
    thread_id: str,
    final_sources: list,
    final_quality_ok: bool,
    final_quality: str,
    elapsed: int,
    answer: str,
    debug_info: DebugInfo,
    ttfb_ms: int = 0,
    first_token_ms: int = 0,
    token_count: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    """Persist the final query metrics using actual debug flags."""
    log_query(
        question=question,
        thread_id=thread_id,
        question_type="knowledge_base",
        retrieval_count=len(final_sources),
        retry_count=debug_info.retry_count,
        quality_ok=final_quality_ok,
        quality_reason=final_quality,
        source_count=len(final_sources),
        elapsed_ms=elapsed,
        answer=answer,
        used_web_search=debug_info.used_web_search,
        used_rerank=debug_info.used_rerank,
        used_rewrite=debug_info.used_rewrite,
        retrieval_k=debug_info.retrieval_k,
        ttfb_ms=ttfb_ms,
        first_token_ms=first_token_ms,
        token_count=token_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        llm_model=get_runtime_setting("llm_model", LLM_MODEL),
    )


def generate_title(question: str) -> str:
    """Use LLM to generate a short conversation title from the first question."""
    try:
        if not _is_configured_api_key(get_runtime_setting("siliconflow_api_key", "")):
            return question[:30]

        llm = _create_auxiliary_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "根据用户的问题，生成一个简短（不超过15字）的对话标题。只返回标题本身，不要加引号和标点。"),
            ("human", question),
        ])
        result = llm.invoke(prompt.format())
        title = str(result.content).strip().strip('"').strip("'")[:30]
        return title if title else question[:30]
    except Exception:
        logger.warning("对话标题生成失败，回退到原始问题。", exc_info=True)
        return question[:30]


def generate_suggested_questions(docs_text: str, max_questions: int = 5) -> list[str]:
    """Use LLM to generate suggested questions from document content."""
    if len(docs_text.strip()) < 50:
        return []
    try:
        if not _is_configured_api_key(get_runtime_setting("siliconflow_api_key", "")):
            return []

        llm = _create_auxiliary_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "根据以下文档内容，生成{max_n}个用户可能想问的问题，每行一个，用中文。只返回问题，不要编号和额外的文字。"),
            ("human", docs_text[:2000]),
        ])
        result = llm.invoke(prompt.format(max_n=max_questions))
        questions = [line.strip().strip('"').strip("'").strip("。") for line in str(result.content).strip().split("\n") if line.strip()]
        return [q for q in questions if len(q) > 4][:max_questions]
    except Exception:
        logger.warning("建议问题生成失败，返回空列表。", exc_info=True)
        return []
