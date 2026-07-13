"""SSE protocol adapter for queued document jobs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from sse_starlette.sse import EventSourceResponse


JobReader = Callable[[str], dict[str, Any] | None]
DEFAULT_POLL_SECONDS = 0.1


def progress_payload(progress: dict[str, Any]) -> dict[str, Any]:
    """Remove the terminal result from progress events."""
    return {key: value for key, value in progress.items() if key != "result"}


def done_payload(job: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Merge a completed job result with the route's fallback response."""
    result = job.get("progress", {}).get("result")
    payload = {**fallback, **result} if isinstance(result, dict) else dict(fallback)
    if fallback.get("existing_version"):
        payload["existing_version"] = True
    payload["job_id"] = job["id"]
    return payload


def _sse_event(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}


def job_event_source(
    job_id: str,
    *,
    fallback_done: dict[str, Any],
    get_job: JobReader,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> EventSourceResponse:
    """Translate persisted job progress into document-import SSE events."""

    async def event_stream():
        last_progress: dict[str, Any] | None = None
        while True:
            job = get_job(job_id)
            if job is None:
                yield _sse_event("error", {"job_id": job_id, "message": "任务不存在"})
                return

            progress = progress_payload(job.get("progress", {}))
            if progress and progress != last_progress:
                last_progress = dict(progress)
                yield _sse_event("progress", progress)

            status = job.get("status")
            if status == "succeeded":
                yield _sse_event("done", done_payload(job, fallback_done))
                return
            if status == "failed":
                yield _sse_event("error", {"job_id": job_id, "message": job.get("error") or "导入任务失败"})
                return
            if status == "canceled":
                yield _sse_event("error", {"job_id": job_id, "message": "导入任务已取消"})
                return

            await asyncio.sleep(poll_seconds)

    return EventSourceResponse(event_stream())
