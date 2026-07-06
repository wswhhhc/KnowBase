"""Background job status routes."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import authorize_workspace_role, get_current_user_or_legacy_api_key, get_knowledge_base
from src.api.models import JobOut
from src.jobs.enqueue import retry_tracked_job
from src.persistence import audit_store, job_store


router = APIRouter()
_KB_MUTATION_JOB_TYPES = {"ingest_file", "ingest_url", "clear_workspace", "rebuild_index"}
_UPLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "knowbase_uploads"


def _is_admin_or_legacy(current_user: dict | None) -> bool:
    return current_user is None or current_user.get("role") == "admin"


def _visible_job_or_404(job_id: str, current_user: dict | None) -> dict:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if not _is_admin_or_legacy(current_user) and job.get("created_by_user_id") != current_user.get("id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    _authorize_job_workspace(job, current_user, "viewer")
    return job


def _authorize_job_workspace(job: dict, current_user: dict | None, minimum_role: str) -> None:
    workspace_id = str(job.get("workspace_id") or "")
    if workspace_id and not _is_admin_or_legacy(current_user):
        authorize_workspace_role(current_user, workspace_id, minimum_role)


def _is_job_visible_in_current_workspace(job: dict, current_user: dict | None) -> bool:
    if _is_admin_or_legacy(current_user):
        return True
    try:
        _authorize_job_workspace(job, current_user, "viewer")
    except HTTPException:
        return False
    return True


def _invalidate_kb_cache_after_successful_mutation(job: dict) -> None:
    if job.get("status") == "succeeded" and job.get("job_type") in _KB_MUTATION_JOB_TYPES:
        get_knowledge_base.cache_clear()


def _cleanup_queued_upload_temp_file(job: dict) -> None:
    if job.get("status") != "queued" or job.get("job_type") != "ingest_file":
        return
    retry_payload = job.get("progress", {}).get("_retry")
    if not isinstance(retry_payload, dict):
        return
    kwargs = retry_payload.get("kwargs")
    if not isinstance(kwargs, dict):
        return
    raw_file_path = kwargs.get("file_path")
    if not isinstance(raw_file_path, str) or not raw_file_path.strip():
        return
    try:
        upload_root = _UPLOAD_TEMP_DIR.resolve()
        file_path = Path(raw_file_path).resolve()
    except (OSError, RuntimeError, ValueError):
        return
    if upload_root != file_path and upload_root not in file_path.parents:
        return
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        return


@router.get("")
async def list_jobs(
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> list[JobOut]:
    owner_id = None if _is_admin_or_legacy(current_user) else str(current_user.get("id") or "")
    jobs = job_store.list_jobs(created_by_user_id=owner_id)
    return [JobOut(**job) for job in jobs if _is_job_visible_in_current_workspace(job, current_user)]


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> JobOut:
    job = _visible_job_or_404(job_id, current_user)
    _invalidate_kb_cache_after_successful_mutation(job)
    return JobOut(**job)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> JobOut:
    job = _visible_job_or_404(job_id, current_user)
    _authorize_job_workspace(job, current_user, "editor")
    if job["status"] not in {"queued", "running", "canceled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已结束，无法取消")
    canceled = job_store.cancel_job(job_id)
    if canceled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if canceled.get("status") == "canceled":
        _cleanup_queued_upload_temp_file(job)
    if job["status"] != "canceled":
        audit_store.record_event(
            action="job.canceled",
            actor_user_id=current_user.get("id") if current_user else None,
            target_type="job",
            target_id=job_id,
            metadata={
                "job_type": canceled.get("job_type", ""),
                "workspace_id": canceled.get("workspace_id", ""),
            },
        )
    return JobOut(**canceled)


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> JobOut:
    job = _visible_job_or_404(job_id, current_user)
    _authorize_job_workspace(job, current_user, "editor")
    try:
        retried = retry_tracked_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="任务队列不可用") from exc
    return JobOut(**retried)
