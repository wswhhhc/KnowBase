"""Documents — upload, URL ingest, source management."""

from __future__ import annotations

import asyncio
import json
import re
import threading

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sse_starlette.sse import EventSourceResponse

from src.api.deps import get_knowledge_base, verify_api_key
from src.api.models import IngestResponse, URLIngestRequest, SourceOut
from src.chat_utils import generate_suggested_questions
from src.rag.models import normalize_source
from src.rag.knowledge_base import KnowledgeBase
from src.utils import save_uploaded_file

router = APIRouter(dependencies=[Depends(verify_api_key)])
_VERSIONED_SOURCE_RE = re.compile(r"^(.+?)\s+\(v\d+\)$")


def _source_identity(source_name: str) -> str:
    """Normalize a source label, stripping the UI-only version suffix when present."""
    match = _VERSIONED_SOURCE_RE.match(source_name)
    if match:
        source_name = match.group(1).strip()
    return normalize_source(source_name)


def _source_exists(kb: KnowledgeBase, source_name: str, workspace_id: str = "") -> bool:
    target = _source_identity(source_name)
    for source_label, _count in kb.source_counts(workspace_id=workspace_id):
        if _source_identity(source_label) == target:
            return True
    return False


def _threaded_event_source(job) -> EventSourceResponse:
    """Run a blocking ingestion job in a thread and stream thread-safe SSE events."""

    async def _event_stream():
        queue: asyncio.Queue[dict] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: str, payload: dict):
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"event": event, "data": json.dumps(payload)},
            )

        def runner():
            try:
                job(emit)
            except Exception as exc:  # pragma: no cover - defensive fallback
                emit("error", {"message": str(exc)})

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()

        while True:
            event = await queue.get()
            yield event
            if event["event"] in {"done", "error"}:
                return

    return EventSourceResponse(_event_stream())


@router.get("/sources")
async def list_sources(
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> list[SourceOut]:
    return [SourceOut(source=s, count=c) for s, c in kb.source_counts(workspace_id=workspace_id)]


@router.get("/check-source")
async def check_source(
    source_name: str,
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> dict:
    """Check if a source name already exists, without modifying any data."""
    return {"exists": _source_exists(kb, source_name, workspace_id=workspace_id)}


@router.post("/upload-stream")
async def upload_file_stream(
    file: UploadFile = File(...),
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    """SSE streaming upload — sends progress events during ingestion."""
    try:
        file_path, source_name = save_uploaded_file(file)
        existing = _source_exists(kb, source_name, workspace_id=workspace_id)

        if existing and not version_mode:
            async def _probe_events():
                yield {"event": "done", "data": json.dumps({
                    "chunk_count": 0,
                    "total_docs": kb.document_count_for_workspace(workspace_id),
                    "message": "来源已存在，请指定 version_mode（replace/append/skip）",
                    "existing_version": True,
                })}
            return EventSourceResponse(_probe_events())

        actual_mode = version_mode or "replace"

        def _run_ingestion(emit):
            def _progress(phase: str, percent: int):
                emit("progress", {"phase": phase, "percent": percent})

            chunk_count = kb.ingest_file(
                str(file_path), source_name=source_name,
                version_mode=actual_mode, progress_callback=_progress,
                workspace_id=workspace_id,
            )
            _total, source_chunks = kb.list_chunks(workspace_id=workspace_id, source=source_name, limit=1000)
            docs_text = " ".join(chunk.content for chunk in source_chunks)
            suggested = generate_suggested_questions(docs_text) if chunk_count > 0 else []
            msg = f"已添加 {chunk_count} 个新段落" if chunk_count else "文件内容无变化，未新增段落"
            emit("progress", {"phase": "done", "percent": 100})
            emit("done", {
                "chunk_count": chunk_count,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": msg,
                "suggested_questions": suggested,
                "existing_version": existing,
            })

        return _threaded_event_source(_run_ingestion)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/ingest-url-stream")
async def ingest_url_stream(
    body: URLIngestRequest,
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    """SSE streaming URL ingestion — sends progress events."""
    try:
        existing = _source_exists(kb, body.url, workspace_id=workspace_id)

        if existing and not version_mode:
            async def _probe_events():
                yield {"event": "done", "data": json.dumps({
                    "chunk_count": 0,
                    "total_docs": kb.document_count_for_workspace(workspace_id),
                    "message": "来源已存在，请指定 version_mode（replace/append/skip）",
                    "existing_version": True,
                })}
            return EventSourceResponse(_probe_events())

        actual_mode = version_mode or "replace"

        def _run_ingestion(emit):
            def _progress(phase: str, percent: int):
                emit("progress", {"phase": phase, "percent": percent})

            chunk_count = kb.ingest_url(
                body.url,
                version_mode=actual_mode,
                progress_callback=_progress,
                workspace_id=workspace_id,
            )
            msg = f"已添加 {chunk_count} 个新段落" if chunk_count else "URL 内容已存在"
            emit("progress", {"phase": "done", "percent": 100})
            emit("done", {
                "chunk_count": chunk_count,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": msg,
                "existing_version": existing,
            })

        return _threaded_event_source(_run_ingestion)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse:
    try:
        file_path, source_name = save_uploaded_file(file)
        existing = _source_exists(kb, source_name, workspace_id=workspace_id)

        # If no version_mode specified and source exists, return probe info without importing
        if existing and not version_mode:
            return IngestResponse(
                chunk_count=0, total_docs=kb.document_count_for_workspace(workspace_id),
                message="来源已存在，请指定 version_mode（replace/append/skip）",
                existing_version=True,
            )

        actual_mode = version_mode or "replace"
        chunk_count = kb.ingest_file(
            str(file_path),
            source_name=source_name,
            version_mode=actual_mode,
            workspace_id=workspace_id,
        )
        _total, source_chunks = kb.list_chunks(workspace_id=workspace_id, source=source_name, limit=1000)
        docs_text = " ".join(chunk.content for chunk in source_chunks)
        suggested = generate_suggested_questions(docs_text) if chunk_count > 0 else []

        msg = f"已添加 {chunk_count} 个新段落" if chunk_count else "文件内容无变化，未新增段落"
        return IngestResponse(
            chunk_count=chunk_count, total_docs=kb.document_count_for_workspace(workspace_id),
            message=msg,
            suggested_questions=suggested,
            existing_version=existing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/ingest-url")
async def ingest_url(
    body: URLIngestRequest,
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse:
    try:
        existing = _source_exists(kb, body.url, workspace_id=workspace_id)

        if existing and not version_mode:
            return IngestResponse(
                chunk_count=0,
                total_docs=kb.document_count_for_workspace(workspace_id),
                message="来源已存在，请指定 version_mode（replace/append/skip）",
                existing_version=True,
            )

        actual_mode = version_mode or "replace"
        chunk_count = kb.ingest_url(body.url, version_mode=actual_mode, workspace_id=workspace_id)
        return IngestResponse(
            chunk_count=chunk_count, total_docs=kb.document_count_for_workspace(workspace_id),
            message=f"已添加 {chunk_count} 个新段落" if chunk_count else "URL 内容已存在",
            existing_version=existing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/source/{source_name:path}")
async def delete_source(
    source_name: str,
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse:
    removed = kb.delete_source(source_name, workspace_id=workspace_id)
    if removed == 0:
        raise HTTPException(404, "来源不存在")
    return IngestResponse(
        chunk_count=removed, total_docs=kb.document_count_for_workspace(workspace_id),
        message=f"已删除 {source_name}（{removed} 个段落）",
    )


@router.post("/clear")
async def clear_kb(
    workspace_id: str = Query(""),
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    removed = kb.clear_workspace(workspace_id=workspace_id)
    return {"ok": True, "message": "知识库已清空", "removed": removed}
