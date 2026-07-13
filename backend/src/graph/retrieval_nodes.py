"""Query rewrite, retrieval, and rerank nodes for the LangGraph workflow."""

from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path
import re
from typing import Literal, Protocol

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from src.config.constants import (
    RERANK_QUERY_LENGTH,
    RERANK_SCORE_GAP_THRESHOLD,
    SCORE_THRESHOLD,
    TOP_K_RERANK,
    TOP_K_RETRIEVAL,
)
from src.config.runtime_overrides import get_runtime_setting
from src.graph import utils as gu
from src.graph.state import GraphState, GraphStateUpdate, RerankDecision
from src.graph.web_search_nodes import tavily_configured as _tavily_configured
from src.rag.models import RetrievalResult, metadata_workspace_id, normalize_source, normalize_workspace_id
from src.utils import extract_context_terms


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

    llm = gu._get_llm(purpose="auxiliary")
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

    docs = [result for result in docs if result.chunk_id not in excluded_set]

    score_by_id = {result.chunk_id: result.score for result in docs}
    doc_by_id = {result.chunk_id: result.document for result in docs}
    enriched_docs: list[Document] = []
    seen_ids: set[str] = set()
    neighbor_window = 2 if short_query else 1
    for result in docs:
        neighbors = kb.get_neighbor_chunks(
            result.chunk_id,
            window=neighbor_window,
            workspace_id=workspace_id,
        )
        if not neighbors:
            neighbor = doc_by_id.get(result.chunk_id)
            if neighbor is not None:
                chunk_id = neighbor.metadata.get("chunk_id", "")
                if chunk_id and chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    enriched_docs.append(neighbor)
            continue
        for neighbor in neighbors:
            chunk_id = neighbor.metadata.get("chunk_id", "")
            if chunk_id and chunk_id not in seen_ids and chunk_id not in excluded_set:
                seen_ids.add(chunk_id)
                enriched_docs.append(neighbor)

    if pinned_set:
        pinned_missing = pinned_set - seen_ids
        if pinned_missing:
            pinned_raw = kb.vector_store.get(
                ids=list(pinned_missing),
                include=["documents", "metadatas"],
            )
            for chunk_id_str, doc_content, doc_meta in zip(
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
                seen_ids.add(chunk_id_str)

    enriched_results = []
    for document in enriched_docs:
        chunk_id = document.metadata.get("chunk_id", "")
        base_score = score_by_id.get(chunk_id, 0.0)
        boost = _document_relevance_boost(document, query, query_terms)
        enriched_results.append(
            RetrievalResult(
                chunk_id=chunk_id,
                document=document,
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

    scores = sorted([document.score for document in docs if hasattr(document, "score")], reverse=True)
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
        no_rerank_limit = top_k
        if len(query) < RERANK_QUERY_LENGTH:
            no_rerank_limit = max(top_k, min(len(docs), 8))
        top_docs = docs[:no_rerank_limit]
        context, sources = gu._format_context(top_docs)
        return {"documents": top_docs, "context": context, "sources": sources, "used_rerank": False}

    doc_ids = {result.chunk_id for result in docs}
    docs_text = "\n\n".join(
        f"ID: {result.chunk_id}\n来源: {result.document.metadata.get('source', '未知来源')}\n内容: {result.document.page_content[:500]}"
        for result in docs
    )
    llm = gu._get_llm(purpose="auxiliary")
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
        fallback_k = top_k_rerank if strategy == "deep" else top_k
        reranked = docs[:fallback_k]

    context, sources = gu._format_context(reranked)
    return {
        "documents": reranked,
        "context": context,
        "sources": sources,
        "used_rerank": True,
        **token_usage,
    }
