"""Documents — upload, URL ingest, source management."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query

from src.api.deps import get_knowledge_base, verify_api_key
from src.api.models import IngestResponse, URLIngestRequest, SourceOut
from src.chat_utils import generate_suggested_questions
from src.kb_models import normalize_source
from src.knowledge_base import KnowledgeBase
from src.utils import save_uploaded_file

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/sources")
async def list_sources(kb: KnowledgeBase = Depends(get_knowledge_base)) -> list[SourceOut]:
    return [SourceOut(source=s, count=c) for s, c in kb.source_counts()]


@router.get("/check-source")
async def check_source(source_name: str, kb: KnowledgeBase = Depends(get_knowledge_base)) -> dict:
    """Check if a source name already exists, without modifying any data."""
    exists = False
    for s, c in kb.source_counts():
        if normalize_source(s) == normalize_source(source_name):
            exists = True
            break
    return {"exists": exists}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    version_mode: str | None = Query(None, regex="^(replace|append|skip)$"),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse:
    try:
        file_path, source_name = save_uploaded_file(file)
        existing = False
        for s, c in kb.source_counts():
            if normalize_source(s) == normalize_source(source_name):
                existing = True
                break

        # If no version_mode specified and source exists, return probe info without importing
        if existing and not version_mode:
            return IngestResponse(
                chunk_count=0, total_docs=kb.document_count,
                message="来源已存在，请指定 version_mode（replace/append/skip）",
                existing_version=True,
            )

        actual_mode = version_mode or "replace"
        chunk_count = kb.ingest_file(str(file_path), source_name=source_name, version_mode=actual_mode)
        docs_text = " ".join(d.page_content for d in kb.all_docs if d.metadata.get("source", "").startswith(source_name.rsplit(".", 1)[0]))
        suggested = generate_suggested_questions(docs_text) if chunk_count > 0 else []

        msg = f"已添加 {chunk_count} 个新段落" if chunk_count else "文件内容无变化，未新增段落"
        return IngestResponse(
            chunk_count=chunk_count, total_docs=kb.document_count,
            message=msg,
            suggested_questions=suggested,
            existing_version=existing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/ingest-url")
async def ingest_url(body: URLIngestRequest, kb: KnowledgeBase = Depends(get_knowledge_base)) -> IngestResponse:
    try:
        chunk_count = kb.ingest_url(body.url)
        return IngestResponse(
            chunk_count=chunk_count, total_docs=kb.document_count,
            message=f"已添加 {chunk_count} 个新段落" if chunk_count else "URL 内容已存在",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/source/{source_name:path}")
async def delete_source(source_name: str, kb: KnowledgeBase = Depends(get_knowledge_base)) -> IngestResponse:
    removed = kb.delete_source(source_name)
    if removed == 0:
        raise HTTPException(404, "来源不存在")
    return IngestResponse(
        chunk_count=removed, total_docs=kb.document_count,
        message=f"已删除 {source_name}（{removed} 个段落）",
    )


@router.post("/clear")
async def clear_kb(kb: KnowledgeBase = Depends(get_knowledge_base)):
    kb.clear()
    return {"ok": True, "message": "工作区已清空"}
