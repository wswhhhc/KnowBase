"""Document ingestion tasks executed by RQ workers."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from src.chat_utils import generate_suggested_questions
from src.persistence import audit_store, job_store
from src.rag.knowledge_base import KnowledgeBase


def collect_suggested_questions(
    kb: KnowledgeBase,
    source_names: list[str],
    *,
    workspace_id: str = "",
) -> list[str]:
    texts: list[str] = []
    seen_sources: set[str] = set()
    for source_name in source_names:
        if source_name in seen_sources:
            continue
        seen_sources.add(source_name)
        _total, source_chunks = kb.list_chunks(
            workspace_id=workspace_id,
            source=source_name,
            limit=1000,
        )
        if source_chunks:
            texts.append(" ".join(chunk.content for chunk in source_chunks))
    docs_text = " ".join(texts).strip()
    return generate_suggested_questions(docs_text) if docs_text else []


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


def _audit_url_import_rejected(
    *,
    job_id: str | None,
    url: str,
    workspace_id: str,
    error: str,
) -> None:
    if not job_id:
        return
    job = job_store.get_job(job_id)
    audit_store.record_event(
        action="url_import.rejected",
        actor_user_id=job.get("created_by_user_id") if job else None,
        target_type="job",
        target_id=job_id,
        metadata={
            "workspace_id": workspace_id,
            "job_type": "ingest_url",
            "error": error,
            **_redacted_url_for_audit(url),
        },
    )


def ingest_url_document(
    *,
    url: str,
    version_mode: str = "replace",
    workspace_id: str = "",
    job_id: str | None = None,
    kb: KnowledgeBase | None = None,
) -> dict:
    knowledge_base = kb or KnowledgeBase()

    def _progress(phase: str, percent: int):
        if job_id:
            job_store.update_job_progress(
                job_id,
                progress={"phase": phase, "percent": percent},
            )

    try:
        chunk_count = knowledge_base.ingest_url(
            url,
            version_mode=version_mode,
            progress_callback=_progress,
            workspace_id=workspace_id,
        )
    except ValueError as exc:
        _audit_url_import_rejected(
            job_id=job_id,
            url=url,
            workspace_id=workspace_id,
            error=str(exc),
        )
        raise
    suggested = collect_suggested_questions(knowledge_base, [url], workspace_id=workspace_id)
    message = f"已添加 {chunk_count} 个新段落" if chunk_count else "URL 内容已存在"
    result = {
        "chunk_count": chunk_count,
        "total_docs": knowledge_base.document_count_for_workspace(workspace_id),
        "message": message,
        "suggested_questions": suggested,
        "existing_version": False,
    }
    if job_id:
        job_store.update_job_progress(
            job_id,
            progress={"phase": "finalizing", "percent": 95, "message": message},
        )
    return result


def ingest_file_document(
    *,
    file_path: str,
    source_name: str,
    version_mode: str = "replace",
    workspace_id: str = "",
    job_id: str | None = None,
    kb: KnowledgeBase | None = None,
) -> dict:
    knowledge_base = kb or KnowledgeBase()

    def _progress(phase: str, percent: int):
        if job_id:
            job_store.update_job_progress(
                job_id,
                progress={"phase": phase, "percent": percent},
            )

    try:
        chunk_count = knowledge_base.ingest_file(
            file_path,
            source_name=source_name,
            version_mode=version_mode,
            progress_callback=_progress,
            workspace_id=workspace_id,
        )
        suggested = collect_suggested_questions(knowledge_base, [source_name], workspace_id=workspace_id)
        message = f"已添加 {chunk_count} 个新段落" if chunk_count else "文件内容无变化，未新增段落"
        result = {
            "chunk_count": chunk_count,
            "total_docs": knowledge_base.document_count_for_workspace(workspace_id),
            "message": message,
            "suggested_questions": suggested,
            "existing_version": False,
        }
        if job_id:
            job_store.update_job_progress(
                job_id,
                progress={"phase": "finalizing", "percent": 95, "message": message},
            )
        return result
    finally:
        Path(file_path).unlink(missing_ok=True)


def clear_workspace_documents(
    *,
    workspace_id: str = "",
    job_id: str | None = None,
    kb: KnowledgeBase | None = None,
) -> dict:
    knowledge_base = kb or KnowledgeBase(require_embeddings=False)
    if job_id:
        job_store.update_job_progress(
            job_id,
            progress={"phase": "clearing", "percent": 50, "message": "正在清空知识库"},
        )

    removed = knowledge_base.clear_workspace(workspace_id=workspace_id)
    return {
        "removed": removed,
        "total_docs": knowledge_base.document_count_for_workspace(workspace_id),
        "message": "知识库已清空",
    }


def rebuild_index_documents(
    *,
    workspace_id: str = "",
    job_id: str | None = None,
    kb: KnowledgeBase | None = None,
) -> dict:
    knowledge_base = kb or KnowledgeBase()
    if job_id:
        job_store.update_job_progress(
            job_id,
            progress={"phase": "rebuilding", "percent": 50, "message": "正在重建索引"},
        )

    total_docs = knowledge_base.rebuild_index(workspace_id=workspace_id)
    return {
        "total_docs": total_docs,
        "message": "索引已重建",
    }
