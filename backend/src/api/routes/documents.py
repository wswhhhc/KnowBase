"""Documents — upload, URL ingest, source management."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sse_starlette.sse import EventSourceResponse

from src.api.deps import get_knowledge_base, require_workspace_editor, require_workspace_viewer
from src.api.models import DemoImportResponse, IngestResponse, JobCreateResponse, URLIngestRequest, SourceOut
from src.api.rate_limit import enforce_document_import_rate_limit
from src.jobs.enqueue import enqueue_tracked_job
from src.persistence import audit_store, job_store
from src.chat_utils import generate_suggested_questions
from src.rag.models import normalize_source
from src.rag.knowledge_base import KnowledgeBase
from src.utils import save_uploaded_file

router = APIRouter()
_VERSIONED_SOURCE_RE = re.compile(r"^(.+?)\s+\(v\d+\)$")
_JOB_SSE_POLL_SECONDS = 0.1


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


def _sse_event(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}


def _progress_payload(progress: dict) -> dict:
    return {key: value for key, value in progress.items() if key != "result"}


def _done_payload(job: dict, fallback: dict) -> dict:
    result = job.get("progress", {}).get("result")
    payload = {**fallback, **result} if isinstance(result, dict) else dict(fallback)
    if fallback.get("existing_version"):
        payload["existing_version"] = True
    payload["job_id"] = job["id"]
    return payload


def _redacted_url_for_audit(raw_url: str) -> dict:
    parsed = urlsplit(raw_url)
    host = parsed.hostname or ""
    netloc_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{netloc_host}:{port}" if port is not None else netloc_host
    return {
        "scheme": parsed.scheme,
        "host": host,
        "url": urlunsplit((parsed.scheme, netloc, parsed.path, "", "")),
    }


def _audit_url_import_queued(
    *,
    actor_user_id: str | None,
    workspace_id: str,
    job_id: str,
    url: str,
    version_mode: str,
    stream: bool,
) -> None:
    audit_store.record_event(
        action="document.url_import_queued",
        actor_user_id=actor_user_id,
        target_type="job",
        target_id=job_id,
        metadata={
            "workspace_id": workspace_id,
            "job_type": "ingest_url",
            "version_mode": version_mode,
            "stream": stream,
            **_redacted_url_for_audit(url),
        },
    )


def _audit_file_import_queued(
    *,
    actor_user_id: str | None,
    workspace_id: str,
    job_id: str,
    source_name: str,
    version_mode: str,
    stream: bool,
) -> None:
    audit_store.record_event(
        action="document.file_import_queued",
        actor_user_id=actor_user_id,
        target_type="job",
        target_id=job_id,
        metadata={
            "workspace_id": workspace_id,
            "job_type": "ingest_file",
            "version_mode": version_mode,
            "stream": stream,
            "source_name": source_name,
        },
    )


def _job_event_source(job_id: str, *, fallback_done: dict) -> EventSourceResponse:
    """Stream progress for an already queued import job."""

    async def _event_stream():
        last_progress: dict | None = None
        while True:
            job = job_store.get_job(job_id)
            if job is None:
                yield _sse_event("error", {"job_id": job_id, "message": "任务不存在"})
                return

            progress = _progress_payload(job.get("progress", {}))
            if progress and progress != last_progress:
                last_progress = dict(progress)
                yield _sse_event("progress", progress)

            status = job.get("status")
            if status == "succeeded":
                yield _sse_event("done", _done_payload(job, fallback_done))
                return
            if status == "failed":
                yield _sse_event(
                    "error",
                    {"job_id": job_id, "message": job.get("error") or "导入任务失败"},
                )
                return
            if status == "canceled":
                yield _sse_event("error", {"job_id": job_id, "message": "导入任务已取消"})
                return

            await asyncio.sleep(_JOB_SSE_POLL_SECONDS)

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
    file_path: str | None = None
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
            Path(file_path).unlink(missing_ok=True)
            return EventSourceResponse(_probe_events())

        actual_mode = version_mode or "replace"
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        job = enqueue_tracked_job(
            job_type="ingest_file",
            target_path="src.jobs.document_tasks:ingest_file_document",
            created_by_user_id=actor_user_id,
            workspace_id=workspace_id,
            kwargs={
                "file_path": str(file_path),
                "source_name": source_name,
                "version_mode": actual_mode,
                "workspace_id": workspace_id,
            },
            inject_job_id=True,
        )
        _audit_file_import_queued(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            job_id=job["id"],
            source_name=source_name,
            version_mode=actual_mode,
            stream=True,
        )
        return _job_event_source(
            job["id"],
            fallback_done={
                "chunk_count": 0,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": "导入任务已完成",
                "suggested_questions": [],
                "existing_version": existing,
            },
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        if file_path:
            Path(file_path).unlink(missing_ok=True)
        raise HTTPException(503, "任务队列不可用") from e


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
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        job = enqueue_tracked_job(
            job_type="ingest_url",
            target_path="src.jobs.document_tasks:ingest_url_document",
            created_by_user_id=actor_user_id,
            workspace_id=workspace_id,
            kwargs={
                "url": body.url,
                "version_mode": actual_mode,
                "workspace_id": workspace_id,
            },
            inject_job_id=True,
        )
        _audit_url_import_queued(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            job_id=job["id"],
            url=body.url,
            version_mode=actual_mode,
            stream=True,
        )
        return _job_event_source(
            job["id"],
            fallback_done={
                "chunk_count": 0,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": "导入任务已完成",
                "suggested_questions": [],
                "existing_version": existing,
            },
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(503, "任务队列不可用") from e


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
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        job = enqueue_tracked_job(
            job_type="ingest_file",
            target_path="src.jobs.document_tasks:ingest_file_document",
            created_by_user_id=actor_user_id,
            workspace_id=workspace_id,
            kwargs={
                "file_path": str(file_path),
                "source_name": source_name,
                "version_mode": actual_mode,
                "workspace_id": workspace_id,
            },
            inject_job_id=True,
        )
        _audit_file_import_queued(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            job_id=job["id"],
            source_name=source_name,
            version_mode=actual_mode,
            stream=False,
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
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        job = enqueue_tracked_job(
            job_type="ingest_url",
            target_path="src.jobs.document_tasks:ingest_url_document",
            created_by_user_id=actor_user_id,
            workspace_id=workspace_id,
            kwargs={
                "url": body.url,
                "version_mode": actual_mode,
                "workspace_id": workspace_id,
            },
            inject_job_id=True,
        )
        _audit_url_import_queued(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            job_id=job["id"],
            url=body.url,
            version_mode=actual_mode,
            stream=False,
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
) -> JobCreateResponse:
    try:
        job = enqueue_tracked_job(
            job_type="clear_workspace",
            target_path="src.jobs.document_tasks:clear_workspace_documents",
            created_by_user_id=str(_workspace_access.get("id")) if _workspace_access else None,
            workspace_id=workspace_id,
            kwargs={"workspace_id": workspace_id},
            inject_job_id=True,
        )
        return JobCreateResponse(job_id=job["id"], job=job)
    except Exception as e:
        raise HTTPException(503, "任务队列不可用") from e


@router.post("/rebuild-index")
async def rebuild_index(
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
) -> JobCreateResponse:
    try:
        job = enqueue_tracked_job(
            job_type="rebuild_index",
            target_path="src.jobs.document_tasks:rebuild_index_documents",
            created_by_user_id=str(_workspace_access.get("id")) if _workspace_access else None,
            workspace_id=workspace_id,
            kwargs={"workspace_id": workspace_id},
            inject_job_id=True,
        )
        return JobCreateResponse(job_id=job["id"], job=job)
    except Exception as e:
        raise HTTPException(503, "任务队列不可用") from e
