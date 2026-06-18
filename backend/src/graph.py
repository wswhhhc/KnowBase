"""LangGraph workflow for routed RAG, conversational memory, web search, and QA checks."""

from __future__ import annotations

from functools import partial
import json
import logging
import re
import sqlite3
import time

logger = logging.getLogger(__name__)
from typing import Generator, Iterable, List, Literal

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from config.settings import (
    CHECKPOINT_DB_PATH,
    ENABLE_QUALITY_CHECK,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_RETRIES,
    RERANK_QUERY_LENGTH,
    RERANK_SCORE_GAP_THRESHOLD,
    SCORE_THRESHOLD,
    SILICONFLOW_BASE_URL,
    TOP_K_RERANK,
    TOP_K_RETRIEVAL,
    require_siliconflow_api_key,
)
from src.graph_state import GraphState, RerankDecision, RouteDecision, QualityDecision
from src.knowledge_base import KnowledgeBase, RetrievalResult
from src.utils import extract_context_terms, json_from_text


_GRAPH_CACHE: dict[int, object] = {}


def _init_checkpointer():
    """Return a persistent SqliteSaver checkpointer.

    Creates the checkpoint DB on first access. The connection lives for
    the process lifetime; LangGraph handles concurrent writes internally.
    """
    import os
    db_dir = os.path.dirname(CHECKPOINT_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)


_CHECKPOINTER = _init_checkpointer()


def _get_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        openai_api_key=require_siliconflow_api_key(),
        openai_api_base=SILICONFLOW_BASE_URL,
    )


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


def detect_question_type(question: str, chat_history: List[tuple[str, str]]) -> str:
    """Regex-based question routing (fallback when LLM classifier is unavailable)."""
    normalized = re.sub(r"\s+", "", question.lower())

    if chat_history:
        if any(re.search(pattern, normalized) for pattern in _SUMMARY_PATTERNS):
            return "conversation_summary"
        if any(re.search(pattern, normalized) for pattern in _MEMORY_PATTERNS):
            return "chat_memory"

    return "knowledge_base"


def route_question(state: GraphState) -> dict:
    """Classify question: run rules first, LLM only for ambiguous cases."""
    history = _messages_to_turns(state.get("messages", []))

    # Rule-based routing first — fast path for obvious cases
    question_type = detect_question_type(state["question"], history)
    if question_type in ("chat_memory", "conversation_summary"):
        search_filter = _route_search_scope(state["question"], question_type)
        return {"question_type": question_type, "search_filter": search_filter}

    # LLM routing for knowledge_base vs clarification ambiguity
    try:
        llm = _get_llm()
        history_text = _format_chat_history(history, limit=3) if history else "（无历史）"
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
        return {"question_type": decision.question_type, "search_filter": search_filter}
    except Exception as exc:
        logger.warning("LLM 路由失败，使用默认路由: %s", exc)

    # LLM failed; default to knowledge_base
    search_filter = _route_search_scope(state["question"], question_type)
    return {"question_type": question_type, "search_filter": search_filter}


# Scope routing rules: (keywords, source_type) pairs
_SCOPE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("考勤", "请假", "制度", "规范", "休假", "加班", "报销", "办公"), "local_file"),
    (("飞书", "文档", "手册"), "local_file"),
]


def _route_search_scope(question: str, question_type: str) -> dict:
    """Route to a search filter based on question content and type."""
    if question_type != "knowledge_base":
        return {}
    normalized = re.sub(r"\s+", "", question.lower())
    for keywords, source_type in _SCOPE_RULES:
        if any(kw in normalized for kw in keywords):
            return {"source_type": source_type}
    return {}


def _messages_to_turns(messages: List[BaseMessage], exclude_last_human: bool = True) -> List[tuple[str, str]]:
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


def _format_chat_history(history: List[tuple[str, str]], limit: int = 6) -> str:
    recent_turns = history[-limit:]
    return "\n".join(
        f"第{i}轮\n用户：{question}\n助手：{answer}"
        for i, (question, answer) in enumerate(recent_turns, 1)
    )



def parse_rerank_decision(text: str, valid_doc_ids: set[str]) -> RerankDecision:
    """Parse and validate a structured rerank decision."""
    try:
        decision = RerankDecision.model_validate(json_from_text(text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return RerankDecision(selected_doc_ids=[])

    return RerankDecision(
        selected_doc_ids=[doc_id for doc_id in decision.selected_doc_ids if doc_id in valid_doc_ids],
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


def route_after_classifier(state: GraphState) -> Literal["rewrite_query", "answer_from_history", "summarize_history", "handle_clarification"]:
    question_type = state.get("question_type", "knowledge_base")
    if question_type == "chat_memory":
        return "answer_from_history"
    if question_type == "conversation_summary":
        return "summarize_history"
    if question_type == "clarification":
        return "handle_clarification"
    return "rewrite_query"


# 指代词正则 — 命中这些问题才需要 LLM 改写，否则直接用原文
_REFERENTIAL_PATTERNS = (
    r"这[些个]", r"那[些个]", r"它[们]?", r"他[们]?", r"她[们]?",
    r"其", r"该", r"此",
    r"刚才", r"刚刚", r"之前", r"前面", r"上一[轮次句]", r"刚[才那]", r"上[一]?[次面轮]",
    r"你知道.*(上次|之前)", r"我.*(刚才|上次|之前)",
)
_REFERRAL_RE = re.compile("|".join(_REFERENTIAL_PATTERNS))

# 简单改写结果缓存：同一个问题 + 相同对话历史 -> 缓存结果
_rewrite_cache: dict[str, str] = {}


def rewrite_query(state: GraphState) -> dict:
    question = state["question"]
    history = _messages_to_turns(state.get("messages", []))

    # 没有对话历史时不需要改写
    if not history:
        return {"rewritten_question": question, "used_rewrite": False}

    # 没有指代词时不需要改写
    is_vague = bool(_REFERRAL_RE.search(question))
    if not is_vague:
        return {"rewritten_question": question, "used_rewrite": False}

    # 缓存命中
    cache_key = f"{question}||{_format_chat_history(history, limit=3)}"
    cached = _rewrite_cache.get(cache_key)
    if cached is not None:
        return {"rewritten_question": cached, "used_rewrite": cached != question}

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是查询改写助手。结合对话历史，把最新问题改写为独立、完整、适合检索知识库的中文问题。保留原文的指代解析，确保改写后的问题包含前文已建立的关键实体和条件。只返回改写后的问题。"),
        ("human", "对话历史：\n{history}\n\n最新问题：{question}"),
    ])
    result = llm.invoke(prompt.format(history=_format_chat_history(history, limit=3), question=question))
    rewritten = str(result.content).strip()
    used_rewrite = rewritten != question
    _rewrite_cache[cache_key] = rewritten

    # 上下文实体扩展：短追问时自动从上一轮用户问题中提取关键实体追加到改写后 query
    if rewritten and len(rewritten) < 15:
        last_user_q = history[-1][0] if history else ""
        if last_user_q:
            terms = extract_context_terms(last_user_q, top_n=3)
            if terms:
                rewritten = f"{rewritten} ({', '.join(terms)})"
                used_rewrite = True

    return {"rewritten_question": rewritten, "used_rewrite": used_rewrite}


def answer_from_history(state: GraphState) -> dict:
    history = _messages_to_turns(state.get("messages", []))
    if not history:
        answer = "当前会话里还没有可参考的历史消息，所以我无法回答这个问题。"
        return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是对话记忆助手。只能依据给定会话历史回答；如果历史不足，明确说明。用中文回答。"),
        ("human", "会话历史：\n{history}\n\n当前问题：{question}"),
    ])
    result = llm.invoke(prompt.format(history=_format_chat_history(history), question=state["question"]))
    answer = str(result.content).strip()
    return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}


def summarize_history(state: GraphState) -> dict:
    history = _messages_to_turns(state.get("messages", []))
    if not history:
        answer = "当前会话还没有足够内容可供总结。"
        return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是对话总结助手。基于会话历史总结关键信息、结论和未解决问题，不要编造。"),
        ("human", "会话历史：\n{history}\n\n用户要求：{question}"),
    ])
    result = llm.invoke(prompt.format(history=_format_chat_history(history), question=state["question"]))
    answer = str(result.content).strip()
    return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}


def _format_context(results: list[RetrievalResult]) -> tuple[str, list[dict]]:
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
        # For user-facing display, strip the contextual retrieval prefix
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


def retrieve_docs(state: GraphState, kb: KnowledgeBase) -> dict:
    query = state.get("rewritten_question") or state["question"]
    strategy = state.get("search_strategy", "balanced")
    retrieval_k = state.get("retrieval_k") or TOP_K_RETRIEVAL
    # deep 模式下扩检索范围
    if strategy == "deep":
        retrieval_k = max(retrieval_k, TOP_K_RETRIEVAL * 3)
    score_threshold = state.get("score_threshold", SCORE_THRESHOLD)
    search_filter = state.get("search_filter") or None
    docs = kb.hybrid_search(
        query,
        k=retrieval_k,
        score_threshold=score_threshold,
        filter=search_filter,
    )

    # Enrich results with neighbor chunks for context continuity.
    # If enrichment yields nothing (e.g. mock KB), fall back to original.
    score_by_id = {r.chunk_id: r.score for r in docs}
    doc_by_id = {r.chunk_id: r.document for r in docs}
    enriched_docs = []
    seen_ids: set[str] = set()
    for result in docs:
        neighbors = kb.get_neighbor_chunks(result.chunk_id, window=1)
        # If get_neighbor_chunks returned nothing, keep the original doc
        if not neighbors:
            n = doc_by_id.get(result.chunk_id)
            if n is not None:
                cid = n.metadata.get("chunk_id", "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    enriched_docs.append(n)
            continue
        for n in neighbors:
            cid = n.metadata.get("chunk_id", "")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                enriched_docs.append(n)

    enriched_results = [
        RetrievalResult(
            chunk_id=d.metadata.get("chunk_id", ""),
            document=d,
            score=score_by_id.get(d.metadata.get("chunk_id", ""), 0.0),
        )
        for d in enriched_docs
    ]

    context, sources = _format_context(enriched_results)
    return {"documents": enriched_results, "context": context, "sources": sources, "retrieval_k": retrieval_k}


def route_after_retrieval(state: GraphState) -> Literal["rerank_docs", "handle_missing_context"]:
    return "rerank_docs" if state.get("documents") else "handle_missing_context"


def route_after_rerank(state: GraphState) -> Literal["generate_answer"]:
    return "generate_answer"


def handle_missing_context(state: GraphState) -> dict:
    question = state.get("rewritten_question") or state["question"]
    answer = (
        "知识库里没有找到足够相关的内容来回答这个问题。"
        "你可以换一种问法，补充更具体的关键词，或者上传包含这部分信息的文档后再试。"
        f"\n\n当前问题：{question}"
    )
    update = {
        "answer": answer,
        "sources": [],
        "quality_ok": False,
        "quality_reason": "没有检索到相关文档。",
        "retry_strategy": "insufficient_context",
    }
    if not state.get("web_search_enabled", False) or state.get("used_web_search", False) or not _tavily_configured():
        update["messages"] = [AIMessage(content=answer)]
    return update


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


def _web_search_context(state: GraphState) -> dict:
    """Search web for the current question and return context."""
    from src.web_search import format_search_results, web_search as _web_search

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


def _tavily_configured() -> bool:
    """Check if Tavily API key is configured for web search."""
    from config.settings import TAVILY_API_KEY, _is_configured_api_key

    return _is_configured_api_key(TAVILY_API_KEY)


def _should_rerank(state: GraphState) -> bool:
    """Determine whether LLM rerank is needed.

    Skip rerank when:
    - search_strategy is 'fast' (never rerank)
    - search_strategy is 'high_quality' (always rerank)
    - candidate count <= TOP_K_RERANK (no selection needed)
    - RRF score gap among candidates is large enough (good separation)
    - Question is short and simple
    """
    strategy = state.get("search_strategy", "balanced")

    # fast: never rerank
    if strategy == "fast":
        return False
    # high_quality: always rerank
    if strategy == "high_quality":
        return True
    # deep: always rerank, wider selection
    if strategy == "deep":
        return True

    docs = state.get("documents", [])
    if len(docs) <= TOP_K_RERANK:
        return False

    # Check RRF score gap among candidates
    scores = sorted(
        [d.score for d in docs if hasattr(d, "score")],
        reverse=True,
    )
    if len(scores) >= 2:
        gap = scores[0] - scores[TOP_K_RERANK - 1] if len(scores) >= TOP_K_RERANK else scores[0] - scores[-1]
        if gap >= RERANK_SCORE_GAP_THRESHOLD:
            return False

    # Check question length
    query = state.get("rewritten_question") or state.get("question", "")
    if len(query) < RERANK_QUERY_LENGTH:
        return False

    return True


def rerank_docs(state: GraphState) -> dict:
    docs = state.get("documents", [])
    if not docs:
        return {}

    strategy = state.get("search_strategy", "balanced")
    top_k = TOP_K_RERANK * 3 if strategy == "deep" else TOP_K_RERANK

    # Skip LLM rerank when not needed — use top candidates directly
    if not _should_rerank(state):
        top = docs[:top_k]
        context, sources = _format_context(top)
        return {"documents": top, "context": context, "sources": sources, "used_rerank": False}

    query = state.get("rewritten_question") or state["question"]
    doc_ids = {result.chunk_id for result in docs}
    docs_text = "\n\n".join(
        f"ID: {result.chunk_id}\n来源: {result.document.metadata.get('source', '未知来源')}\n内容: {result.document.page_content[:500]}"
        for result in docs
    )
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是文档重排器。只输出 JSON，格式为 {{\"selected_doc_ids\":[\"chunk_id\"],\"reason\":\"简短原因\"}}。"),
        ("human", "问题：{query}\n最多选择 {k} 个最相关文档。\n\n候选文档：\n{docs_text}"),
    ])

    try:
        result = llm.invoke(prompt.format(query=query, k=top_k, docs_text=docs_text))
        decision = parse_rerank_decision(str(result.content), doc_ids)
    except Exception as exc:
        logger.warning("LLM 精排失败，回退到原始排序: %s", exc)
        decision = RerankDecision(selected_doc_ids=[])

    by_id = {result.chunk_id: result for result in docs}
    reranked = [by_id[doc_id] for doc_id in decision.selected_doc_ids[:top_k]]
    if not reranked:
        reranked = docs[:top_k]

    context, sources = _format_context(reranked)
    return {"documents": reranked, "context": context, "sources": sources, "used_rerank": True}


def generate_answer(state: GraphState) -> dict:
    context = state.get("context", "")
    web_context = state.get("web_context", "")
    web_search_error = state.get("web_search_error", "")
    question = state.get("rewritten_question") or state["question"]
    used_web_search = state.get("used_web_search", False)
    history = _messages_to_turns(state.get("messages", []))
    strategy = state.get("search_strategy", "balanced")

    # Merge web search results into context
    if web_context:
        context = f"{context}\n\n{web_context}" if context else web_context
    elif used_web_search and web_search_error and not context:
        answer = (
            "知识库里没有找到足够相关的内容，联网搜索也没有可用结果。"
            f"\n\n联网搜索状态：{web_search_error}"
        )
        return {
            "answer": answer,
            "sources": [],
            "quality_ok": False,
            "quality_reason": web_search_error,
        }

    system_msg = "你是知识库问答助手。"
    if strategy == "deep" and not (used_web_search and web_context):
        system_msg += "参考文档涵盖了全文多个部分，请综合回答。"
    if used_web_search and web_context:
        system_msg += "可以基于知识库和网络搜索结果回答。在回答中引用来源时，使用 [1]、[2] 等编号标注，编号对应参考文档列表中的顺序。多个引用用逗号分隔如 [1,2]。用中文回答。保持与对话历史中已给出信息的一致性，如果同一实体已有过描述，不要自相矛盾。"
    else:
        system_msg += "只能基于参考文档回答；证据不足就说不知道。在回答中引用参考文档时，使用 [1]、[2] 等编号标注来源，编号对应上方参考文档列表中的编号。例如：根据文档说明，该值为 42[1]。多个引用用逗号分隔如 [1,2]。每个关键事实都应标注来源。用中文回答。保持与对话历史中已给出信息的一致性，如果同一实体已有过描述，不要自相矛盾。"

    llm = _get_llm()
    if history:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "对话历史：\n{history}\n\n参考文档：\n{context}\n\n用户问题：{question}"),
        ])
        result = llm.invoke(prompt.format(history=_format_chat_history(history, limit=3), context=context, question=question))
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "参考文档：\n{context}\n\n用户问题：{question}"),
        ])
        result = llm.invoke(prompt.format(context=context, question=question))
    answer = str(result.content).strip()
    sources = state.get("sources", [])
    if web_context:
        sources = sources + [
            {
                "index": len(sources) + i,
                "chunk_id": item.get("url", ""),
                "source": item.get("title") or item.get("url") or "网络来源",
                "chunk_index": "",
                "page": "",
                "content": item.get("content", "")[:300],
                "score": item.get("score"),
                "vector_score": None,
                "bm25_score": None,
                "url": item.get("url", ""),
            }
            for i, item in enumerate(state.get("web_search_results", []), 1)
        ]
    return {"answer": answer, "sources": sources}


def _rule_check_quality(state: GraphState) -> dict | None:
    """Rule-based quality checks. Returns update dict if rule matches, None otherwise."""
    answer = state.get("answer", "")
    context = state.get("context", "")
    web_context = state.get("web_context", "")
    sources = state.get("sources", [])
    used_web_search = state.get("used_web_search", False)
    documents = state.get("documents", [])

    # No documents retrieved → insufficient context
    if not documents and not web_context:
        return {
            "quality_ok": False,
            "quality_reason": "未检索到相关文档。",
            "retry_strategy": "insufficient_context",
        }

    # No sources referenced in answer but we have docs → likely missing citation
    if sources and not any(
        s.get("source") in answer or (s.get("chunk_id") or "") in answer
        for s in sources[:3]
    ):
        # Not a hard fail — let LLM decide
        pass

    # Answer is too short with no substance
    if len(answer.strip()) < 10 and sources:
        return {
            "quality_ok": False,
            "quality_reason": "回答过短。",
            "retry_strategy": "expand_retrieval",
        }

    # If web search was already used and we have sources, accept
    if used_web_search and sources:
        return {
            "quality_ok": True,
            "quality_reason": "基于网络搜索的回答。",
            "retry_strategy": "none",
        }

    return None  # No rule matched, fall through to LLM


def check_quality(state: GraphState) -> dict:
    if state.get("question_type") != "knowledge_base" or not ENABLE_QUALITY_CHECK:
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

    # Rule-based check first
    rule_result = _rule_check_quality(state)
    if rule_result is not None:
        update = {
            **rule_result,
            "retry_count": retry_count + 1,
        }
        if rule_result.get("quality_ok") or retry_count + 1 >= MAX_RETRIES:
            update["messages"] = [AIMessage(content=answer)]
            return update
        # Check if we should trigger web search
        if not used_web_search and state.get("web_search_enabled", False) and _tavily_configured():
            update["retry_strategy"] = "web_search"
            update["retry_count"] = retry_count
        return update

    # LLM quality check — sample to reduce LLM calls
    # 联网搜索可用时不做采样，确保质量不合格能触发搜索兜底
    strategy = state.get("search_strategy", "balanced")
    web_search_available = state.get("web_search_enabled", False) and _tavily_configured()
    if strategy != "high_quality" and not web_search_available and hash(question + answer) % 3 != 0:
        # 采样通过：只有 1/3 的概率走 LLM 质量检查
        decision = QualityDecision(quality_passed=True, quality_reason="质量检查采样跳过。")
    else:
        llm = _get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是回答质量审核员。只输出 JSON，格式为 {{\"quality_passed\": true/false, \"quality_reason\": \"原因\", \"retry_strategy\": \"none|rewrite_query|expand_retrieval|insufficient_context\"}}。"),
            ("human", "问题：{question}\n\n参考文档：{context}\n\n回答：{answer}"),
        ])

        try:
            result = llm.invoke(prompt.format(question=question, context=context[:3000], answer=answer))
            decision = parse_quality_decision(str(result.content))
        except Exception as exc:
            logger.warning("LLM 质量检查失败，保守放行: %s", exc)
            decision = QualityDecision(quality_passed=True, quality_reason="质量检查调用失败，保守放行。")

    update = {
        "quality_ok": decision.quality_passed,
        "quality_reason": decision.quality_reason,
        "retry_strategy": decision.retry_strategy,
        "retry_count": retry_count + 1,
    }
    if decision.quality_passed or retry_count + 1 >= MAX_RETRIES:
        update["messages"] = [AIMessage(content=answer)]
        return update

    if used_web_search:
        update["messages"] = [AIMessage(content=answer)]
        update["retry_strategy"] = "none"
        return update

    # Quality failed — check if we should try web search first
    if not used_web_search and state.get("web_search_enabled", False) and _tavily_configured():
        update["retry_strategy"] = "web_search"
        update["retry_count"] = retry_count  # Don't count web_search attempt toward retry_count
        return update

    strategy = decision.retry_strategy
    if strategy == "expand_retrieval":
        update["retrieval_k"] = min(
            (state.get("retrieval_k") or TOP_K_RETRIEVAL) + TOP_K_RETRIEVAL,
            TOP_K_RETRIEVAL * 4,
        )
        update["score_threshold"] = None
    elif strategy == "rewrite_query":
        update["score_threshold"] = None
    return update


def should_retry(state: GraphState) -> Literal["web_search", "rewrite_query", "retrieve_docs", "finalize"]:
    if state.get("quality_ok", True):
        return "finalize"
    if state.get("retry_strategy") == "web_search":
        return "web_search"
    if state.get("retry_count", 0) < MAX_RETRIES:
        retry_strategy = state.get("retry_strategy", "expand_retrieval")
        if retry_strategy == "rewrite_query":
            return "rewrite_query"
        return "retrieve_docs"
    return "finalize"


def _compute_evidence(state: GraphState) -> tuple[str, str, str]:
    """Compute (evidence_level, outcome_category, evidence_summary) from state."""
    sources = state.get("sources", [])
    used_web = state.get("used_web_search", False)
    quality_ok = state.get("quality_ok", True)
    quality_reason = state.get("quality_reason", "")
    qtype = state.get("question_type", "knowledge_base")

    # Count local vs web sources
    local_count = sum(1 for s in sources if not s.get("url"))
    web_count = sum(1 for s in sources if s.get("url"))

    # Outcome category
    if qtype == "clarification":
        return "none", "vague_question", "问题描述比较模糊，建议补充具体信息"
    if qtype in ("chat_memory", "conversation_summary"):
        return "strong", "success", "基于对话历史回答"

    if not local_count and not used_web:
        return "none", "no_docs", "知识库中没有找到相关内容"
    if not local_count and used_web and not web_count:
        return "none", "web_empty", "知识库和联网搜索都没有找到相关内容"

    # Quality-based
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

    # Quality not OK
    if quality_reason and "未检索" in quality_reason:
        return "none", "no_docs", "知识库中没有找到相关内容"
    if used_web and not web_count:
        return "none", "web_empty", "知识库和联网搜索都没有找到足够相关的内容"
    return "weak", "weak_evidence", f"检索到 {local_count} 个相关片段，但证据不够充分"


def finalize(state: GraphState) -> dict:
    """Compute user-facing evidence metadata before returning."""
    evidence_level, outcome_category, evidence_summary = _compute_evidence(state)
    return {
        "evidence_level": evidence_level,
        "outcome_category": outcome_category,
        "evidence_summary": evidence_summary,
    }


def build_graph(knowledge_base: KnowledgeBase):
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    workflow.add_node("route_question", route_question)
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("answer_from_history", answer_from_history)
    workflow.add_node("summarize_history", summarize_history)
    workflow.add_node("retrieve_docs", partial(retrieve_docs, kb=knowledge_base))
    workflow.add_node("handle_missing_context", handle_missing_context)
    workflow.add_node("handle_clarification", handle_clarification)
    workflow.add_node("rerank_docs", rerank_docs)
    workflow.add_node("web_search", _web_search_context)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("check_quality", check_quality)
    workflow.add_node("finalize", finalize)

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
        route_after_retrieval,
        {"rerank_docs": "rerank_docs", "handle_missing_context": "handle_missing_context"},
    )
    workflow.add_edge("rerank_docs", "generate_answer")
    workflow.add_edge("generate_answer", "check_quality")
    workflow.add_edge("answer_from_history", "finalize")
    workflow.add_edge("summarize_history", "finalize")
    workflow.add_edge("handle_clarification", "finalize")
    workflow.add_conditional_edges(
        "handle_missing_context",
        lambda s: "web_search" if not s.get("used_web_search") and s.get("web_search_enabled", False) and _tavily_configured() else "finalize",
        {"web_search": "web_search", "finalize": "finalize"},
    )
    workflow.add_edge("web_search", "generate_answer")
    workflow.add_conditional_edges(
        "check_quality",
        should_retry,
        {"web_search": "web_search", "rewrite_query": "rewrite_query", "retrieve_docs": "retrieve_docs", "finalize": "finalize"},
    )
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=_CHECKPOINTER)


def get_graph(knowledge_base: KnowledgeBase):
    """Return a cached compiled graph for a knowledge base instance."""
    cache_key = id(knowledge_base)
    if cache_key not in _GRAPH_CACHE:
        _GRAPH_CACHE[cache_key] = build_graph(knowledge_base)
    return _GRAPH_CACHE[cache_key]


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
        "retrieval_k": TOP_K_RETRIEVAL,
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
        "evidence_level": "none",
        "evidence_summary": "",
        "outcome_category": "success",
        "used_rerank": False,
        "used_rewrite": False,
    }


def _graph_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _state_with_overrides(question: str, **overrides) -> GraphState:
    state = _initial_state(question)
    state.update(overrides)
    return state


def _stream_query(question: str, thread_id: str, knowledge_base: KnowledgeBase, **state_overrides) -> Iterable[dict]:
    graph = get_graph(knowledge_base)
    for update in graph.stream(_state_with_overrides(question, **state_overrides), config=_graph_config(thread_id), stream_mode="updates"):
        yield update


def _stream_query_with_tokens(
    question: str, thread_id: str, knowledge_base: KnowledgeBase, **state_overrides
) -> Generator[tuple[str, dict], None, None]:
    """Stream graph updates AND token-level LLM output.

    Yields (mode, data) tuples where mode is "updates" or "messages".
    """
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
) -> dict | Iterable[dict] | Generator[tuple[str, dict], None, None]:
    """Execute one question against the cached LangGraph workflow.

    Args:
        stream: If True, yield node-level updates.
        stream_tokens: If True, yield (mode, data) tuples with token-level LLM output.
        web_search_enabled: If True, enable web search fallback.
        search_strategy: 'fast', 'balanced', or 'high_quality'.
    """
    overrides = {
        "web_search_enabled": web_search_enabled,
        "search_strategy": search_strategy,
    }
    if stream_tokens:
        return _stream_query_with_tokens(question, thread_id, knowledge_base, **overrides)
    if stream:
        return _stream_query(question, thread_id, knowledge_base, **overrides)

    graph = get_graph(knowledge_base)
    state = _state_with_overrides(question, **overrides)
    return graph.invoke(state, config=_graph_config(thread_id))
