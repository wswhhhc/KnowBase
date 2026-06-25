"""Knowledge base browser — stats, search, chunk listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_knowledge_base, verify_api_key
from src.api.models import KBChunk, KBStats, HotspotEntry, KBConfig
from src.kb_models import normalize_source
from src.knowledge_base import KnowledgeBase
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP

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
    docs = kb.all_docs
    if source:
        docs = [d for d in docs if d.metadata.get("source", "") == normalize_source(source)]
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
    return KBConfig(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)


@router.get("/hotspots")
async def hotspots(kb: KnowledgeBase = Depends(get_knowledge_base)) -> list[HotspotEntry]:
    return kb.get_hotspots()
