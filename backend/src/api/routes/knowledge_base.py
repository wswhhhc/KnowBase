"""Knowledge base browser — stats, search, chunk listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import get_knowledge_base, verify_api_key
from src.api.models import KBChunk, KBStats, HotspotEntry, KBConfig
from src import graph_nodes as gn
from src.kb_models import normalize_source
from src.kb_models import RetrievalResult
from src.knowledge_base import KnowledgeBase
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, TOP_K_RETRIEVAL, get_runtime_setting


class DebugSearchRequest(BaseModel):
    query: str
    k: int = 5
    search_strategy: str = "balanced"


class DebugSearchResult(BaseModel):
    chunk_id: str
    source: str
    content: str
    score: float | None = None
    vector_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    vector_rank: int | None = None
    bm25_rank: int | None = None
    rrf_rank: int | None = None
    rerank_rank: int | None = None


class DebugSearchResponse(BaseModel):
    strategy: str
    vector_results: list[DebugSearchResult]
    bm25_results: list[DebugSearchResult]
    fused_results: list[DebugSearchResult]


def _resolve_debug_search_params(strategy: str, requested_k: int, default_retrieval_k: int) -> tuple[int, int]:
    """Map UI strategy names to retrieval depth knobs for debug search."""
    requested_k = max(1, requested_k)

    if strategy == "fast":
        retrieval_k = requested_k
        vector_candidate_k = max(requested_k * 2, 10)
    elif strategy == "high_quality":
        retrieval_k = max(requested_k, default_retrieval_k * 2)
        vector_candidate_k = max(retrieval_k * 4, 40)
    elif strategy == "deep":
        retrieval_k = max(requested_k, default_retrieval_k * 3)
        vector_candidate_k = max(retrieval_k * 5, 60)
    else:
        retrieval_k = max(requested_k, default_retrieval_k)
        vector_candidate_k = max(retrieval_k * 3, 20)

    return retrieval_k, vector_candidate_k


router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/stats")
async def stats(kb: KnowledgeBase = Depends(get_knowledge_base)) -> KBStats:
    sources = kb.source_counts()
    return KBStats(
        chunk_count=sum(c for _, c in sources),
        source_count=len(sources),
        total_chars=sum(len(d.page_content) for d in kb.all_docs),
    )


@router.get("/chunks")
async def chunks(
    source: str = Query(""), search: str = Query(""),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> dict:
    # Trigger lazy load from Chroma before accessing all_docs
    kb.source_counts()
    docs = kb.all_docs
    if source:
        source = normalize_source(source)
        # Parse optional version suffix: "doc.txt (v2)"
        import re as _re
        version_filter = None
        m = _re.match(r"^(.+?)\s+\(v(\d+)\)$", source)
        if m:
            source = m.group(1).strip()
            version_filter = f"v{m.group(2)}"
        docs = [
            d for d in docs
            if d.metadata.get("source", "") == source
            and (version_filter is None or d.metadata.get("version") == version_filter)
        ]
    if search:
        keywords = [kw.strip().lower() for kw in search.split() if kw.strip()]
        docs = [d for d in docs if any(kw in d.page_content.lower() for kw in keywords)]
    total = len(docs)
    page = docs[skip : skip + limit]
    return {
        "total": total,
        "items": [
            KBChunk(
                source=d.metadata.get("source", ""),
                chunk_index=d.metadata.get("chunk_index", 0),
                chunk_id=d.metadata.get("chunk_id", ""),
                page=d.metadata.get("page"),
                content=d.page_content,
                original_content=d.metadata.get("original_content"),
                section=d.metadata.get("section"),
            )
            for d in page
        ],
    }


@router.get("/sources")
async def list_source_names(kb: KnowledgeBase = Depends(get_knowledge_base)) -> list[str]:
    return sorted(s for s, _c in kb.source_counts())


@router.get("/config")
async def kb_config() -> KBConfig:
    return KBConfig(
        chunk_size=get_runtime_setting("chunk_size", CHUNK_SIZE),
        chunk_overlap=get_runtime_setting("chunk_overlap", CHUNK_OVERLAP),
    )


@router.get("/hotspots")
async def hotspots(kb: KnowledgeBase = Depends(get_knowledge_base)) -> list[HotspotEntry]:
    return kb.get_hotspots()


@router.post("/debug-search")
async def debug_search(body: DebugSearchRequest, kb: KnowledgeBase = Depends(get_knowledge_base)) -> DebugSearchResponse:
    """Run a debug hybrid search that returns per-document scores (vector, BM25, RRF)."""
    strategy = body.search_strategy or "balanced"
    default_retrieval_k = get_runtime_setting("top_k_retrieval", TOP_K_RETRIEVAL)
    retrieval_k, vector_candidate_k = _resolve_debug_search_params(
        strategy,
        body.k,
        default_retrieval_k,
    )

    try:
        breakdown = kb.debug_search_breakdown(
            body.query,
            k=retrieval_k,
            vector_candidate_k=vector_candidate_k,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    vector_results = breakdown.get("vector_results", [])[:body.k]
    bm25_results = breakdown.get("bm25_results", [])[:body.k]
    fused_results = breakdown.get("fused_results", [])[:body.k]

    vector_ranks = {result.chunk_id: index + 1 for index, result in enumerate(vector_results)}
    bm25_ranks = {result.chunk_id: index + 1 for index, result in enumerate(bm25_results)}
    rrf_ranks = {result.chunk_id: index + 1 for index, result in enumerate(fused_results)}
    fused_by_id = {result.chunk_id: result for result in fused_results}

    def _serialize(result: RetrievalResult) -> DebugSearchResult:
        chunk_id = result.chunk_id
        fused_match = fused_by_id.get(chunk_id)
        vector_score = result.vector_score
        bm25_score = result.bm25_score
        return DebugSearchResult(
            chunk_id=chunk_id,
            source=result.document.metadata.get("source", ""),
            content=result.document.page_content[:300],
            score=result.score,
            vector_score=vector_score,
            bm25_score=bm25_score,
            rrf_score=fused_match.score if fused_match is not None else None,
            vector_rank=vector_ranks.get(chunk_id),
            bm25_rank=bm25_ranks.get(chunk_id),
            rrf_rank=rrf_ranks.get(chunk_id),
            rerank_rank=None,
        )

    return DebugSearchResponse(
        strategy=strategy,
        vector_results=[_serialize(result) for result in vector_results],
        bm25_results=[_serialize(result) for result in bm25_results],
        fused_results=[_serialize(result) for result in fused_results],
    )
