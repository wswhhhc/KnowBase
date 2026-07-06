"""Documents — upload, URL ingest, source management."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sse_starlette.sse import EventSourceResponse

from src.api.deps import get_knowledge_base, require_workspace_editor, require_workspace_viewer
from src.api.models import DemoImportResponse, IngestResponse, JobCreateResponse, URLIngestRequest, SourceOut
from src.api.rate_limit import enforce_document_import_rate_limit
from src.jobs.enqueue import enqueue_tracked_job
from src.chat_utils import generate_suggested_questions
from src.rag.models import normalize_source
from src.rag.knowledge_base import KnowledgeBase
from src.utils import save_uploaded_file

router = APIRouter()
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


def _collect_suggested_questions(
    kb: KnowledgeBase,
    source_names: list[str],
    *,
    workspace_id: str = "",
) -> list[str]:
    texts: list[str] = []
    seen_sources: set[str] = set()
    for source_name in source_names:
        normalized = normalize_source(source_name)
        if normalized in seen_sources:
            continue
        seen_sources.add(normalized)
        _total, source_chunks = kb.list_chunks(
            workspace_id=workspace_id,
            source=source_name,
            limit=1000,
        )
        if source_chunks:
            texts.append(" ".join(chunk.content for chunk in source_chunks))
    docs_text = " ".join(texts).strip()
    return generate_suggested_questions(docs_text) if docs_text else []


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
    _workspace_access: dict | None = Depends(require_workspace_viewer),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> list[SourceOut]:
    return [SourceOut(source=s, count=c) for s, c in kb.source_counts(workspace_id=workspace_id)]


@router.get("/check-source")
async def check_source(
    source_name: str,
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_viewer),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> dict:
    """Check if a source name already exists, without modifying any data."""
    return {"exists": _source_exists(kb, source_name, workspace_id=workspace_id)}


@router.post(
    "/upload-stream",
    responses={429: {"description": "请求过于频繁"}},
)
async def upload_file_stream(
    file: UploadFile = File(...),
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
    _rate_limit: None = Depends(enforce_document_import_rate_limit),
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
            suggested = _collect_suggested_questions(kb, [source_name], workspace_id=workspace_id)
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


@router.post(
    "/ingest-url-stream",
    responses={429: {"description": "请求过于频繁"}},
)
async def ingest_url_stream(
    body: URLIngestRequest,
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
    _rate_limit: None = Depends(enforce_document_import_rate_limit),
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
            suggested = _collect_suggested_questions(kb, [body.url], workspace_id=workspace_id)
            msg = f"已添加 {chunk_count} 个新段落" if chunk_count else "URL 内容已存在"
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


@router.post(
    "/upload",
    responses={429: {"description": "请求过于频繁"}},
)
async def upload_file(
    file: UploadFile = File(...),
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
    _rate_limit: None = Depends(enforce_document_import_rate_limit),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse | JobCreateResponse:
    file_path: str | None = None
    try:
        file_path, source_name = save_uploaded_file(file)
        existing = _source_exists(kb, source_name, workspace_id=workspace_id)

        # If no version_mode specified and source exists, return probe info without importing
        if existing and not version_mode:
            Path(file_path).unlink(missing_ok=True)
            return IngestResponse(
                chunk_count=0, total_docs=kb.document_count_for_workspace(workspace_id),
                message="来源已存在，请指定 version_mode（replace/append/skip）",
                existing_version=True,
            )

        actual_mode = version_mode or "replace"
        job = enqueue_tracked_job(
            job_type="ingest_file",
            target_path="src.jobs.document_tasks:ingest_file_document",
            created_by_user_id=str(_workspace_access.get("id")) if _workspace_access else None,
            workspace_id=workspace_id,
            kwargs={
                "file_path": str(file_path),
                "source_name": source_name,
                "version_mode": actual_mode,
                "workspace_id": workspace_id,
            },
            inject_job_id=True,
        )
        return JobCreateResponse(job_id=job["id"], job=job)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        if file_path:
            Path(file_path).unlink(missing_ok=True)
        raise HTTPException(503, "任务队列不可用") from e


@router.post(
    "/ingest-url",
    responses={429: {"description": "请求过于频繁"}},
)
async def ingest_url(
    body: URLIngestRequest,
    version_mode: str | None = Query(None, pattern="^(replace|append|skip)$"),
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
    _rate_limit: None = Depends(enforce_document_import_rate_limit),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse | JobCreateResponse:
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
        job = enqueue_tracked_job(
            job_type="ingest_url",
            target_path="src.jobs.document_tasks:ingest_url_document",
            created_by_user_id=str(_workspace_access.get("id")) if _workspace_access else None,
            workspace_id=workspace_id,
            kwargs={
                "url": body.url,
                "version_mode": actual_mode,
                "workspace_id": workspace_id,
            },
            inject_job_id=True,
        )
        return JobCreateResponse(job_id=job["id"], job=job)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(503, "任务队列不可用") from e


@router.post("/import-demo")
async def import_demo_documents(
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> DemoImportResponse:
    try:
        chunk_count, imported_sources = kb.import_demo_documents(workspace_id=workspace_id)
        suggested = _collect_suggested_questions(kb, imported_sources, workspace_id=workspace_id)
        message = (
            f"已导入 {len(imported_sources)} 份示例资料"
            if chunk_count > 0
            else "示例资料已在当前工作区就绪"
        )
        return DemoImportResponse(
            chunk_count=chunk_count,
            total_docs=kb.document_count_for_workspace(workspace_id),
            message=message,
            imported_sources=imported_sources,
            suggested_questions=suggested,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/source/{source_name:path}")
async def delete_source(
    source_name: str,
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
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
    _workspace_access: dict | None = Depends(require_workspace_editor),
    kb: KnowledgeBase = Depends(get_knowledge_base),
):
    removed = kb.clear_workspace(workspace_id=workspace_id)
    return {"ok": True, "message": "知识库已清空", "removed": removed}
