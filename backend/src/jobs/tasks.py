"""Tracked RQ task wrappers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from src.persistence import audit_store, job_store


def _record_job_status_event(job: dict, action: str) -> None:
    audit_store.record_event(
        action=action,
        actor_user_id=job.get("created_by_user_id"),
        target_type="job",
        target_id=job["id"],
        metadata={
            "job_type": job.get("job_type", ""),
            "workspace_id": job.get("workspace_id", ""),
            "attempts": job.get("attempts", 0),
        },
    )


def _load_callable(target_path: str):
    module_name, separator, attribute_name = target_path.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("target_path must use 'module:function' format")
    target = getattr(import_module(module_name), attribute_name)
    if not callable(target):
        raise TypeError("target_path does not resolve to a callable")
    return target


def run_tracked_job(
    job_id: str,
    target_path: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> Any:
    job = job_store.mark_job_running(job_id)
    if job is None:
        raise ValueError("job not found")
    if job["status"] != "running":
        return None
    try:
        result = _load_callable(target_path)(*(args or []), **(kwargs or {}))
    except Exception as exc:
        failed = job_store.mark_job_failed(job_id, error=str(exc))
        _record_job_status_event(failed or job, "job.failed")
        raise
    progress = {"phase": "done", "percent": 100}
    if isinstance(result, dict):
        progress["result"] = result
    succeeded = job_store.mark_job_succeeded(job_id, progress=progress)
    _record_job_status_event(succeeded or job, "job.succeeded")
    return result
