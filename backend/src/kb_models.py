"""Knowledge base data models — retrieval results, fusion scores, and helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document


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


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_id(source: str, chunk_index: int, content_hash: str) -> str:
    return f"{normalize_source(source)}:{chunk_index}:{content_hash[:16]}"


def normalize_source(source: str) -> str:
    """Produce a stable source identifier.

    For URLs the full address is preserved (``https://example.com/page``).
    For local file paths only the basename is kept (``report.pdf``).
    Idempotent — calling again on an already normalized value is a no-op.
    """
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return Path(source).name


def infer_source_type(source: str) -> str:
    """Infer source_type from a source identifier."""
    if source.startswith("http://") or source.startswith("https://"):
        return "web_page"
    return "local_file"


def document_chunk_id(doc: Document) -> str:
    existing = doc.metadata.get("chunk_id")
    if existing:
        return str(existing)
    source = normalize_source(doc.metadata.get("source", "unknown"))
    chunk_index = int(doc.metadata.get("chunk_index", 0))
    c_hash = doc.metadata.get("content_hash") or content_hash(doc.page_content)
    cid = chunk_id(source, chunk_index, c_hash)
    doc.metadata.setdefault("source", source)
    doc.metadata.setdefault("chunk_index", chunk_index)
    doc.metadata.setdefault("content_hash", c_hash)
    doc.metadata.setdefault("chunk_id", cid)
    return cid


# Alias for backwards-compatible import in knowledge_base.py
compute_content_hash = content_hash
