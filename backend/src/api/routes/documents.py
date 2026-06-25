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


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    version_mode: str = Query("replace", regex="^(replace|append|skip)$"),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse:
    try:
        file_path, source_name = save_uploaded_file(file)
        # Check if source already exists
        existing_count = 0
        existing = False
        for s, c in kb.source_counts():
            if normalize_source(s) == normalize_source(source_name):
                existing = True
                existing_count = c
                break

        chunk_count = kb.ingest_file(str(file_path), source_name=source_name, version_mode=version_mode)
        docs_text = " ".join(d.page_content for d in kb.all_docs if d.metadata.get("source", "").startswith(source_name.rsplit(".", 1)[0]))
        suggested = generate_suggested_questions(docs_text) if chunk_count > 0 else []

        msg = f"已添加 {chunk_count} 个新片段" if chunk_count else "文件内容无变化，未新增片段"
        return IngestResponse(
            chunk_count=chunk_count, total_docs=kb.document_count,
            message=msg,
            suggested_questions=suggested,
            existing_version=existing,
            version_count=existing_count,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/ingest-url")
async def ingest_url(body: URLIngestRequest, kb: KnowledgeBase = Depends(get_knowledge_base)) -> IngestResponse:
    try:
        chunk_count = kb.ingest_url(body.url)
        return IngestResponse(
            chunk_count=chunk_count, total_docs=kb.document_count,
            message=f"已添加 {chunk_count} 个新片段" if chunk_count else "URL 内容已存在",
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
        message=f"已删除 {source_name}（{removed} 个片段）",
    )


@router.post("/clear")
async def clear_kb(kb: KnowledgeBase = Depends(get_knowledge_base)):
    kb.clear()
    return {"ok": True, "message": "知识库已清空"}
