"""Documents — upload, URL ingest, source management."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query

from src.api.deps import get_knowledge_base, require_workspace_editor, require_workspace_viewer
from src.api.document_job_stream import done_event_source, job_event_source
from src.api.models import DemoImportResponse, IngestResponse, JobCreateResponse, URLIngestRequest, SourceOut
from src.api.rate_limit import enforce_document_import_rate_limit
from src.jobs.enqueue import enqueue_tracked_job
from src.persistence import audit_store, job_store
from src.rag.knowledge_base import KnowledgeBase
from src.services.document_audit import (
    record_demo_imported,
    record_file_import_queued,
    record_source_deleted,
    record_url_import_queued,
)
from src.services.document_import_service import source_exists, submit_file_import, submit_url_import
from src.services.document_job_service import enqueue_clear_workspace, enqueue_rebuild_index
from src.services.document_operations import delete_source as delete_source_operation
from src.services.document_operations import import_demo_documents as import_demo_operation
from src.utils import save_uploaded_file

router = APIRouter()


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
    return {"exists": source_exists(kb, source_name, workspace_id=workspace_id)}


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
    file_owned_by_job = False
    try:
        file_path, source_name = save_uploaded_file(file)
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        submission = submit_file_import(
            kb,
            file_path=str(file_path),
            source_name=source_name,
            version_mode=version_mode,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            enqueue_job=enqueue_tracked_job,
        )
        if submission.job is None:
            Path(file_path).unlink(missing_ok=True)
            return done_event_source({
                "chunk_count": 0,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": "来源已存在，请指定 version_mode（replace/append/skip）",
                "existing_version": True,
            })

        job = submission.job
        file_owned_by_job = True
        actual_mode = submission.version_mode
        record_file_import_queued(
            audit_store.record_event,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            job_id=job["id"],
            source_name=source_name,
            version_mode=actual_mode,
            stream=True,
        )
        return job_event_source(
            job["id"],
            fallback_done={
                "chunk_count": 0,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": "导入任务已完成",
                "suggested_questions": [],
                "existing_version": submission.existing_version,
            },
            get_job=job_store.get_job,
        )
    except ValueError as e:
        if file_path and not file_owned_by_job:
            Path(file_path).unlink(missing_ok=True)
        raise HTTPException(400, str(e))
    except Exception as e:
        if file_path and not file_owned_by_job:
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
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        submission = submit_url_import(
            kb,
            url=body.url,
            version_mode=version_mode,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            enqueue_job=enqueue_tracked_job,
        )
        if submission.job is None:
            return done_event_source({
                "chunk_count": 0,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": "来源已存在，请指定 version_mode（replace/append/skip）",
                "existing_version": True,
            })

        job = submission.job
        actual_mode = submission.version_mode
        record_url_import_queued(
            audit_store.record_event,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            job_id=job["id"],
            url=body.url,
            version_mode=actual_mode,
            stream=True,
        )
        return job_event_source(
            job["id"],
            fallback_done={
                "chunk_count": 0,
                "total_docs": kb.document_count_for_workspace(workspace_id),
                "message": "导入任务已完成",
                "suggested_questions": [],
                "existing_version": submission.existing_version,
            },
            get_job=job_store.get_job,
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
    file_owned_by_job = False
    try:
        file_path, source_name = save_uploaded_file(file)
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        submission = submit_file_import(
            kb,
            file_path=str(file_path),
            source_name=source_name,
            version_mode=version_mode,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            enqueue_job=enqueue_tracked_job,
        )
        if submission.job is None:
            Path(file_path).unlink(missing_ok=True)
            return IngestResponse(
                chunk_count=0, total_docs=kb.document_count_for_workspace(workspace_id),
                message="来源已存在，请指定 version_mode（replace/append/skip）",
                existing_version=True,
            )

        job = submission.job
        file_owned_by_job = True
        actual_mode = submission.version_mode
        record_file_import_queued(
            audit_store.record_event,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            job_id=job["id"],
            source_name=source_name,
            version_mode=actual_mode,
            stream=False,
        )
        return JobCreateResponse(job_id=job["id"], job=job)
    except ValueError as e:
        if file_path and not file_owned_by_job:
            Path(file_path).unlink(missing_ok=True)
        raise HTTPException(400, str(e))
    except Exception as e:
        if file_path and not file_owned_by_job:
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
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        submission = submit_url_import(
            kb,
            url=body.url,
            version_mode=version_mode,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            enqueue_job=enqueue_tracked_job,
        )
        if submission.job is None:
            return IngestResponse(
                chunk_count=0,
                total_docs=kb.document_count_for_workspace(workspace_id),
                message="来源已存在，请指定 version_mode（replace/append/skip）",
                existing_version=True,
            )

        job = submission.job
        actual_mode = submission.version_mode
        record_url_import_queued(
            audit_store.record_event,
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
        result = import_demo_operation(kb, workspace_id=workspace_id)
        response = DemoImportResponse(
            chunk_count=result.chunk_count,
            total_docs=result.total_docs,
            message=result.message,
            imported_sources=result.imported_sources,
            suggested_questions=result.suggested_questions,
        )
        record_demo_imported(
            audit_store.record_event,
            actor_user_id=str(_workspace_access.get("id")) if _workspace_access else None,
            workspace_id=workspace_id,
            imported_sources=result.imported_sources,
            chunk_count=result.chunk_count,
        )
        return response
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/source/{source_name:path}")
async def delete_source(
    source_name: str,
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> IngestResponse:
    result = delete_source_operation(kb, source_name, workspace_id=workspace_id)
    if result is None:
        raise HTTPException(404, "来源不存在")
    record_source_deleted(
        audit_store.record_event,
        actor_user_id=str(_workspace_access.get("id")) if _workspace_access else None,
        workspace_id=workspace_id,
        source_name=source_name,
        removed_chunks=result.chunk_count,
    )
    return IngestResponse(
        chunk_count=result.chunk_count,
        total_docs=result.total_docs,
        message=result.message,
    )


@router.post("/clear")
async def clear_kb(
    workspace_id: str = Query(""),
    _workspace_access: dict | None = Depends(require_workspace_editor),
) -> JobCreateResponse:
    try:
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        job = enqueue_clear_workspace(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            enqueue_job=enqueue_tracked_job,
            record_event=audit_store.record_event,
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
        actor_user_id = str(_workspace_access.get("id")) if _workspace_access else None
        job = enqueue_rebuild_index(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            enqueue_job=enqueue_tracked_job,
            record_event=audit_store.record_event,
        )
        return JobCreateResponse(job_id=job["id"], job=job)
    except Exception as e:
        raise HTTPException(503, "任务队列不可用") from e
