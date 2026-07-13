"""Application service for submitting document import jobs."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from src.rag.models import normalize_source


class SourceCatalog(Protocol):
    def source_counts(self, workspace_id: str = "") -> list[tuple[str, int]]: ...


EnqueueJob = Callable[..., dict[str, Any]]
_VERSIONED_SOURCE_RE = re.compile(r"^(.+?)\s+\(v\d+\)$")


@dataclass(frozen=True)
class ImportSubmission:
    existing_version: bool
    version_mode: str | None
    job: dict[str, Any] | None


def source_identity(source_name: str) -> str:
    """Normalize a source label while ignoring the UI-only version suffix."""
    match = _VERSIONED_SOURCE_RE.match(source_name)
    if match:
        source_name = match.group(1).strip()
    return normalize_source(source_name)


def source_exists(catalog: SourceCatalog, source_name: str, *, workspace_id: str = "") -> bool:
    target = source_identity(source_name)
    return any(
        source_identity(source_label) == target
        for source_label, _count in catalog.source_counts(workspace_id=workspace_id)
    )


def submit_file_import(
    catalog: SourceCatalog,
    *,
    file_path: str,
    source_name: str,
    version_mode: str | None,
    workspace_id: str,
    actor_user_id: str | None,
    enqueue_job: EnqueueJob,
) -> ImportSubmission:
    existing = source_exists(catalog, source_name, workspace_id=workspace_id)
    if existing and not version_mode:
        return ImportSubmission(existing_version=True, version_mode=None, job=None)

    actual_mode = version_mode or "replace"
    job = enqueue_job(
        job_type="ingest_file",
        target_path="src.jobs.document_tasks:ingest_file_document",
        created_by_user_id=actor_user_id,
        workspace_id=workspace_id,
        kwargs={
            "file_path": file_path,
            "source_name": source_name,
            "version_mode": actual_mode,
            "workspace_id": workspace_id,
        },
        inject_job_id=True,
    )
    return ImportSubmission(existing_version=existing, version_mode=actual_mode, job=job)


def submit_url_import(
    catalog: SourceCatalog,
    *,
    url: str,
    version_mode: str | None,
    workspace_id: str,
    actor_user_id: str | None,
    enqueue_job: EnqueueJob,
) -> ImportSubmission:
    existing = source_exists(catalog, url, workspace_id=workspace_id)
    if existing and not version_mode:
        return ImportSubmission(existing_version=True, version_mode=None, job=None)

    actual_mode = version_mode or "replace"
    job = enqueue_job(
        job_type="ingest_url",
        target_path="src.jobs.document_tasks:ingest_url_document",
        created_by_user_id=actor_user_id,
        workspace_id=workspace_id,
        kwargs={"url": url, "version_mode": actual_mode, "workspace_id": workspace_id},
        inject_job_id=True,
    )
    return ImportSubmission(existing_version=existing, version_mode=actual_mode, job=job)
