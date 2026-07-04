"""LangGraph workflow node functions — query rewrite, retrieval, rerank, answer, quality check."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import zlib
from collections import OrderedDict
from typing import Literal, Protocol

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from src.config.settings import (
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
    TAVILY_API_KEY,
    _is_configured_api_key,
    get_runtime_setting,
    require_siliconflow_api_key,
)
from src.graph import utils as gu
from src.graph.finalization_nodes import compute_evidence as _compute_evidence, finalize
from src.graph.generation_nodes import generate_answer
from src.graph.history_nodes import answer_from_history, summarize_history
from src.graph.state import GraphSource, GraphState, GraphStateUpdate, QualityDecision, RerankDecision
from src.graph.web_search_nodes import tavily_configured as _tavily_configured, web_search_context as _web_search_context
from src.rag.models import RetrievalResult, metadata_workspace_id, normalize_source, normalize_workspace_id
from src.utils import extract_context_terms, json_from_text


logger = logging.getLogger(__name__)


class _VectorStoreLike(Protocol):
    def get(self, ids: list[str], include: list[str]) -> dict[str, list[object] | None]: ...


class _GraphKnowledgeBaseLike(Protocol):
    vector_store: _VectorStoreLike

    def hybrid_search(
        self,
        query: str,
        k: int,
        score_threshold: float | None = None,
        filter: object | None = None,
        workspace_id: str | None = None,
    ) -> list[RetrievalResult]: ...

    def get_neighbor_chunks(self, chunk_id: str, window: int = 1, workspace_id: str | None = None) -> list[Document]: ...


# ── Query rewriting ──────────────────────────────────────────────────

_REFERENTIAL_PATTERNS = (
    r"这[些个]", r"那[些个]", r"它[们]?", r"他[们]?", r"她[们]?",
    r"其", r"该", r"此",
    r"刚才", r"刚刚", r"之前", r"前面", r"上一[轮次句]", r"刚[才那]", r"上[一]?[次面轮]",
    r"你知道.*(上次|之前)", r"我.*(刚才|上次|之前)",
)
_REFERRAL_RE = re.compile("|".join(_REFERENTIAL_PATTERNS))

_rewrite_cache: OrderedDict[str, str] = OrderedDict()
_REWRITE_CACHE_MAX = 1000


def rewrite_query(state: GraphState) -> GraphStateUpdate:
    question = state["question"]
    history = gu._messages_to_turns(state.get("messages", []))

    if not history:
        return {"rewritten_question": question, "used_rewrite": False}

    is_vague = bool(_REFERRAL_RE.search(question))
    if not is_vague:
        return {"rewritten_question": question, "used_rewrite": False}

    cache_key = f"{question}||{gu._format_chat_history(history, limit=3)}"
    cached = _rewrite_cache.get(cache_key)
    if cached is not None:
        _rewrite_cache.move_to_end(cache_key)
        return {"rewritten_question": cached, "used_rewrite": cached != question}

    llm = gu._get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是查询改写助手。结合对话历史，把最新问题改写为独立、完整、适合检索工作区的中文问题。保留原文的指代解析，确保改写后的问题包含前文已建立的关键实体和条件。只返回改写后的问题。"),
        ("human", "对话历史：\n{history}\n\n最新问题：{question}"),
    ])
    result = llm.invoke(prompt.format(history=gu._format_chat_history(history, limit=3), question=question))
    rewritten = str(result.content).strip()
    used_rewrite = rewritten != question
    _rewrite_cache[cache_key] = rewritten
    if len(_rewrite_cache) > _REWRITE_CACHE_MAX:
        _rewrite_cache.popitem(last=False)

    if rewritten and len(rewritten) < 15:
        last_user_q = history[-1][0] if history else ""
        if last_user_q:
            terms = extract_context_terms(last_user_q, top_n=3)
            if terms:
                rewritten = f"{rewritten} ({', '.join(terms)})"
                used_rewrite = True

    return {
        "rewritten_question": rewritten,
        "used_rewrite": used_rewrite,
        **gu.extract_token_usage(result),
    }


# ── Retrieval ────────────────────────────────────────────────────────


def _normalize_match_text(text: str) -> str:
    return re.sub(r"[\s_./\\\-《》“”\"'‘’：:，,。！？!?；;（）()\[\]【】]+", "", text.lower())


def _query_terms(query: str, top_n: int = 6) -> list[str]:
    terms = extract_context_terms(query, top_n=top_n)
    if not terms:
        rough_terms = re.split(r"[\s，,。！？!?；;：:（）()\[\]【】]+", query)
        terms = [term.strip().lower() for term in rough_terms if len(term.strip()) >= 2]

    seen: set[str] = set()
    ordered_terms: list[str] = []
    for term in terms:
        norm = _normalize_match_text(term)
        if len(norm) < 2 or norm in seen:
            continue
        seen.add(norm)
        ordered_terms.append(norm)
    return ordered_terms


def _document_relevance_boost(doc: Document, query: str, query_terms: list[str]) -> float:
    query_norm = _normalize_match_text(query)
    short_query = len(query_norm) <= RERANK_QUERY_LENGTH or len(query_terms) <= 4

    source = normalize_source(str(doc.metadata.get("source", "")))
    source_stem = Path(source).stem
    source_norm = _normalize_match_text(source)
    source_stem_norm = _normalize_match_text(source_stem)
    section_norm = _normalize_match_text(str(doc.metadata.get("section", "")))
    content_text = str(doc.metadata.get("original_content") or doc.page_content or "")
    content_norm = _normalize_match_text(content_text)

    bonus = 0.0

    if query_norm:
        if source_stem_norm and source_stem_norm in query_norm:
            bonus += 0.08
        if section_norm and section_norm in query_norm:
            bonus += 0.06
        if short_query and query_norm in content_norm:
            bonus += 0.08

    content_hits = 0
    source_hits = 0
    section_hits = 0
    for term in query_terms:
        if term in content_norm:
            content_hits += 1
        if term in source_norm or (source_stem_norm and term in source_stem_norm):
            source_hits += 1
        if term in section_norm:
            section_hits += 1

    if short_query:
        if content_hits >= 2:
            bonus += 0.24
        elif content_hits == 1:
            bonus += 0.08
    elif content_hits:
        bonus += min(content_hits, 4) * 0.015
    if source_hits:
        bonus += min(source_hits, 3) * 0.08
    if section_hits:
        bonus += min(section_hits, 3) * 0.06
    if short_query and (content_hits + source_hits + section_hits) >= max(2, len(query_terms)):
        bonus += 0.08

    return bonus


def retrieve_docs(state: GraphState, kb: _GraphKnowledgeBaseLike) -> GraphStateUpdate:
    query = state.get("rewritten_question") or state["question"]
    strategy = state.get("search_strategy", "balanced")
    default_retrieval_k = get_runtime_setting("top_k_retrieval", TOP_K_RETRIEVAL)
    retrieval_k = state.get("retrieval_k") or default_retrieval_k
    if strategy == "deep":
        retrieval_k = max(retrieval_k, default_retrieval_k * 3)
    score_threshold = state.get("score_threshold", SCORE_THRESHOLD)
    search_filter = state.get("search_filter") or None
    workspace_id = state.get("workspace_id", "")
    pinned_ids = state.get("pinned_chunk_ids", []) or []
    excluded_ids = state.get("excluded_chunk_ids", []) or []
    excluded_set = set(excluded_ids)
    pinned_set = set(pinned_ids)
    query_terms = _query_terms(query)
    short_query = len(_normalize_match_text(query)) <= RERANK_QUERY_LENGTH or len(query_terms) <= 4

    docs = kb.hybrid_search(
        query,
        k=retrieval_k,
        score_threshold=score_threshold,
        filter=search_filter,
        workspace_id=workspace_id,
    )

    # Apply exclusion filter
    docs = [r for r in docs if r.chunk_id not in excluded_set]

    score_by_id = {r.chunk_id: r.score for r in docs}
    doc_by_id = {r.chunk_id: r.document for r in docs}
    enriched_docs = []
    seen_ids: set[str] = set()
    neighbor_window = 2 if short_query else 1
    for result in docs:
        neighbors = kb.get_neighbor_chunks(
            result.chunk_id,
            window=neighbor_window,
            workspace_id=workspace_id,
        )
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
            if cid and cid not in seen_ids and cid not in excluded_set:
                seen_ids.add(cid)
                enriched_docs.append(n)

    # Force-include pinned chunks even if they never hit the top-K
    if pinned_set:
        pinned_missing = pinned_set - seen_ids
        if pinned_missing:
            pinned_raw = kb.vector_store.get(
                ids=list(pinned_missing),
                include=["documents", "metadatas"],
            )
            for cid_str, doc_content, doc_meta in zip(
                pinned_raw.get("ids", []),
                pinned_raw.get("documents", []) or [],
                pinned_raw.get("metadatas", []) or [],
            ):
                if not doc_content:
                    continue
                metadata = dict(doc_meta or {})
                if metadata_workspace_id(metadata) != normalize_workspace_id(workspace_id):
                    continue
                doc = Document(page_content=doc_content, metadata=metadata)
                enriched_docs.append(doc)
                seen_ids.add(cid_str)

    enriched_results = []
    for d in enriched_docs:
        chunk_id = d.metadata.get("chunk_id", "")
        base_score = score_by_id.get(chunk_id, 0.0)
        boost = _document_relevance_boost(d, query, query_terms)
        enriched_results.append(
            RetrievalResult(
                chunk_id=chunk_id,
                document=d,
                score=base_score + boost,
            )
        )
    enriched_results.sort(key=lambda item: item.score, reverse=True)

    context, sources = gu._format_context(enriched_results)
    return {"documents": enriched_results, "context": context, "sources": sources, "retrieval_k": retrieval_k}


def route_after_retrieval(state: GraphState) -> Literal["rerank_docs", "handle_missing_context"]:
    return "rerank_docs" if state.get("documents") else "handle_missing_context"


def route_after_rerank(state: GraphState) -> Literal["generate_answer"]:
    return "generate_answer"


def handle_missing_context(state: GraphState) -> GraphStateUpdate:
    question = state.get("rewritten_question") or state["question"]
    answer = (
        "工作区里没有找到足够相关的内容来回答这个问题。"
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


# ── Rerank ───────────────────────────────────────────────────────────


def _should_rerank(state: GraphState) -> bool:
    strategy = state.get("search_strategy", "balanced")
    top_k_rerank = get_runtime_setting("top_k_rerank", TOP_K_RERANK)

    if strategy == "fast":
        return False
    if strategy in ("high_quality", "deep"):
        return True

    docs = state.get("documents", [])
    if len(docs) <= top_k_rerank:
        return False

    scores = sorted(
        [d.score for d in docs if hasattr(d, "score")],
        reverse=True,
    )
    if len(scores) >= 2:
        gap = scores[0] - scores[top_k_rerank - 1] if len(scores) >= top_k_rerank else scores[0] - scores[-1]
        if gap >= RERANK_SCORE_GAP_THRESHOLD:
            return False

    query = state.get("rewritten_question") or state.get("question", "")
    if len(query) < RERANK_QUERY_LENGTH:
        return False

    return True


def rerank_docs(state: GraphState) -> GraphStateUpdate:
    docs = state.get("documents", [])
    if not docs:
        return {}

    strategy = state.get("search_strategy", "balanced")
    query = state.get("rewritten_question") or state["question"]
    top_k_rerank = get_runtime_setting("top_k_rerank", TOP_K_RERANK)
    top_k = top_k_rerank * 3 if strategy == "deep" else top_k_rerank

    if not _should_rerank(state):
        # Short entity/relation questions often have noisy top-3 vector hits.
        # If retrieval already found more candidates, keep a wider context slice
        # instead of truncating before the relevant chunk reaches the prompt.
        no_rerank_limit = top_k
        if len(query) < RERANK_QUERY_LENGTH:
            no_rerank_limit = max(top_k, min(len(docs), 8))
        top = docs[:no_rerank_limit]
        context, sources = gu._format_context(top)
        return {"documents": top, "context": context, "sources": sources, "used_rerank": False}

    doc_ids = {result.chunk_id for result in docs}
    docs_text = "\n\n".join(
        f"ID: {result.chunk_id}\n来源: {result.document.metadata.get('source', '未知来源')}\n内容: {result.document.page_content[:500]}"
        for result in docs
    )
    llm = gu._get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是文档重排器。只输出 JSON，格式为 {{\"selected_doc_ids\":[\"chunk_id\"],\"reason\":\"简短原因\"}}。"),
        ("human", "问题：{query}\n最多选择 {k} 个最相关文档。\n\n候选文档：\n{docs_text}"),
    ])

    try:
        result = llm.invoke(prompt.format(query=query, k=top_k, docs_text=docs_text))
        decision = gu.parse_rerank_decision(str(result.content), doc_ids)
        token_usage = gu.extract_token_usage(result)
    except Exception as exc:
        logger.warning("LLM 精排失败，回退到原始排序: %s", exc)
        decision = RerankDecision(selected_doc_ids=[])
        token_usage = {}

    by_id = {result.chunk_id: result for result in docs}
    reranked = [by_id[doc_id] for doc_id in decision.selected_doc_ids[:top_k]]
    if not reranked:
        reranked = docs[:top_k]

    context, sources = gu._format_context(reranked)
    return {
        "documents": reranked,
        "context": context,
        "sources": sources,
        "used_rerank": True,
        **token_usage,
    }


# ── Quality check ────────────────────────────────────────────────────


def _rule_check_quality(state: GraphState) -> GraphStateUpdate | None:
    answer = state.get("answer", "")
    context = state.get("context", "")
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
        s.get("source") in answer or (s.get("chunk_id") or "") in answer
        for s in sources[:3]
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

    rule_result = _rule_check_quality(state)
    if rule_result is not None:
        update = {
            **rule_result,
            "retry_count": retry_count + 1,
        }
        if rule_result.get("quality_ok") or retry_count + 1 >= MAX_RETRIES:
            update["messages"] = [AIMessage(content=answer)]
            return update
        if not used_web_search and state.get("web_search_enabled", False) and _tavily_configured():
            update["retry_strategy"] = "web_search"
            update["retry_count"] = retry_count
        return update

    strategy = state.get("search_strategy", "balanced")
    web_search_available = state.get("web_search_enabled", False) and _tavily_configured()
    # 确定性采样：adler32 保证同一输入在不同进程/重启后结果一致
    token_usage = {}
    if strategy != "high_quality" and not web_search_available and zlib.adler32((question + answer).encode("utf-8")) % 3 != 0:
        decision = QualityDecision(quality_passed=True, quality_reason="质量检查采样跳过。")
    else:
        llm = gu._get_llm()
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

    strategy = decision.retry_strategy
    if strategy == "expand_retrieval":
        default_retrieval_k = get_runtime_setting("top_k_retrieval", TOP_K_RETRIEVAL)
        update["retrieval_k"] = min(
            (state.get("retrieval_k") or default_retrieval_k) + default_retrieval_k,
            default_retrieval_k * 4,
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


