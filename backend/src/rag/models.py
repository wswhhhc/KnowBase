"""Knowledge base data models — retrieval results, fusion scores, and helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from pydantic import BaseModel


@dataclass(frozen=True)
class RetrievalResult:
    """A retrieved chunk plus retrieval diagnostics."""

    chunk_id: str
    document: Document
    score: float
    vector_score: float | None = None
    bm25_score: float | None = None


@dataclass(frozen=True)
class FusionScore:
    """RRF output before mapping back to documents."""

    chunk_id: str
    score: float
    vector_score: float | None = None
    bm25_score: float | None = None


class KBChunk(BaseModel):
    source: str
    chunk_index: int
    chunk_id: str
    page: int | None = None
    content: str
    original_content: str | None = None
    section: str | None = None


class HotspotEntry(BaseModel):
    chunk_id: str
    source: str
    hits: int
    content_preview: str


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_workspace_id(workspace_id: str | None) -> str:
    return workspace_id or ""


def chunk_id(source: str, chunk_index: int, content_hash: str) -> str:
    return f"{normalize_source(source)}:{chunk_index}:{content_hash[:16]}"


def workspace_chunk_id(workspace_id: str | None, source: str, chunk_index: int, content_hash: str) -> str:
    base_chunk_id = chunk_id(source, chunk_index, content_hash)
    normalized_workspace_id = normalize_workspace_id(workspace_id)
    if not normalized_workspace_id:
        return base_chunk_id
    return f"{normalized_workspace_id}::{base_chunk_id}"


def normalize_source(source: str) -> str:
    """Produce a stable source identifier.

    For URLs the full address is preserved (``https://example.com/page``).
    For local file paths only the basename is kept (``report.pdf``).
    Idempotent — calling again on an already normalized value is a no-op.
    """
    if source.startswith("http://") or source.startswith("https://"):
        return source
    # Normalize Windows-style backslashes first so basename extraction
    # behaves consistently on Linux/macOS CI runners too.
    return Path(source.replace("\\", "/")).name


def canonical_source_from_metadata(metadata: dict, default: str = "unknown") -> str:
    """Return the canonical source identifier for persisted metadata.

    Legacy Chroma rows may have stored only a basename in ``source`` for web
    pages while preserving the full URL separately in ``url``. In that case the
    URL should win so source identity remains stable and collision-free.
    """
    source = str(metadata.get("source", default))
    if source and "/" not in source and not source.startswith("http"):
        url = metadata.get("url")
        if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
            source = url
    return normalize_source(source)


def infer_source_type(source: str) -> str:
    """Infer source_type from a source identifier."""
    if source.startswith("http://") or source.startswith("https://"):
        return "web_page"
    return "local_file"


def metadata_workspace_id(metadata: dict, default: str = "") -> str:
    return normalize_workspace_id(metadata.get("workspace_id", default))


def document_chunk_id(doc: Document) -> str:
    existing = doc.metadata.get("chunk_id")
    if existing and not any(key in doc.metadata for key in ("source", "chunk_index", "url", "content_hash", "workspace_id")):
        return str(existing)
    source = canonical_source_from_metadata(doc.metadata)
    chunk_index = int(doc.metadata.get("chunk_index", 0))
    c_hash = doc.metadata.get("content_hash") or content_hash(doc.page_content)
    workspace_id = metadata_workspace_id(doc.metadata)
    expected_prefix = f"{workspace_id}::{source}:{chunk_index}:" if workspace_id else f"{source}:{chunk_index}:"
    if existing and str(existing).startswith(expected_prefix):
        return str(existing)
    if existing:
        doc.metadata.setdefault("legacy_chunk_id", str(existing))
    cid = workspace_chunk_id(workspace_id, source, chunk_index, c_hash)
    doc.metadata["source"] = source
    doc.metadata["workspace_id"] = workspace_id
    doc.metadata.setdefault("chunk_index", chunk_index)
    doc.metadata.setdefault("content_hash", c_hash)
    doc.metadata["chunk_id"] = cid
    return cid


# Alias for backwards-compatible import in knowledge_base.py
compute_content_hash = content_hash
