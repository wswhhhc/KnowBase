"""Audit helpers for document operations.

The helpers keep document-specific metadata out of HTTP routes while allowing
callers to inject the persistence function used to record an event.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit


AuditRecorder = Callable[..., Any]


def redacted_url_for_audit(raw_url: str) -> dict[str, str]:
    """Return a URL identity safe to persist in audit metadata."""
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


def source_audit_identity(source_name: str) -> tuple[str, dict[str, str]]:
    """Build an audit target without persisting URL secrets."""
    parsed = urlsplit(source_name)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        redacted = redacted_url_for_audit(source_name)
        return redacted["url"], {
            "source_name": redacted["url"],
            "source_scheme": redacted["scheme"],
            "source_host": redacted["host"],
        }
    return source_name, {"source_name": source_name}


def record_url_import_queued(
    record_event: AuditRecorder,
    *,
    actor_user_id: str | None,
    workspace_id: str,
    job_id: str,
    url: str,
    version_mode: str,
    stream: bool,
) -> None:
    record_event(
        action="document.url_import_queued",
        actor_user_id=actor_user_id,
        target_type="job",
        target_id=job_id,
        metadata={
            "workspace_id": workspace_id,
            "job_type": "ingest_url",
            "version_mode": version_mode,
            "stream": stream,
            **redacted_url_for_audit(url),
        },
    )


def record_file_import_queued(
    record_event: AuditRecorder,
    *,
    actor_user_id: str | None,
    workspace_id: str,
    job_id: str,
    source_name: str,
    version_mode: str,
    stream: bool,
) -> None:
    record_event(
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


def record_workspace_mutation_queued(
    record_event: AuditRecorder,
    *,
    action: str,
    actor_user_id: str | None,
    workspace_id: str,
    job_id: str,
    job_type: str,
) -> None:
    record_event(
        action=action,
        actor_user_id=actor_user_id,
        target_type="job",
        target_id=job_id,
        metadata={"workspace_id": workspace_id, "job_type": job_type},
    )


def record_demo_imported(
    record_event: AuditRecorder,
    *,
    actor_user_id: str | None,
    workspace_id: str,
    imported_sources: list[str],
    chunk_count: int,
) -> None:
    record_event(
        action="document.demo_imported",
        actor_user_id=actor_user_id,
        target_type="workspace",
        target_id=workspace_id,
        metadata={
            "workspace_id": workspace_id,
            "imported_sources": imported_sources,
            "chunk_count": chunk_count,
        },
    )


def record_source_deleted(
    record_event: AuditRecorder,
    *,
    actor_user_id: str | None,
    workspace_id: str,
    source_name: str,
    removed_chunks: int,
) -> None:
    target_id, source_metadata = source_audit_identity(source_name)
    record_event(
        action="document.source_deleted",
        actor_user_id=actor_user_id,
        target_type="source",
        target_id=target_id,
        metadata={
            "workspace_id": workspace_id,
            **source_metadata,
            "removed_chunks": removed_chunks,
        },
    )
