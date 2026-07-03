"""Shared knowledge-base state and workspace-aware filtering helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import re

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from src.rag.models import metadata_workspace_id, normalize_source, normalize_workspace_id


_VERSIONED_SOURCE_RE = re.compile(r"^(.+?)\s+\(v(\d+)\)$")


def workspace_matches(metadata: dict, workspace_id: str | None) -> bool:
    if workspace_id is None:
        return True
    return metadata_workspace_id(metadata) == normalize_workspace_id(workspace_id)


def parse_versioned_source_label(source_name: str) -> tuple[str, str | None]:
    normalized_source = normalize_source(source_name)
    match = _VERSIONED_SOURCE_RE.match(normalized_source)
    if not match:
        return normalized_source, None
    return match.group(1).strip(), f"v{match.group(2)}"


def search_keywords(query: str) -> list[str]:
    return [keyword.strip().lower() for keyword in query.split() if keyword.strip()]


class KnowledgeBaseState:
    """Mutable KB index state shared across ingestion, retrieval, and catalog services."""

    def __init__(self, initial_chunk_ids: Iterable[str] | None = None):
        self.all_docs: list[Document] = []
        self.doc_by_id: dict[str, Document] = {}
        self.existing_chunk_ids: set[str] = set(initial_chunk_ids or [])
        self.bm25_corpus: list[list[str]] = []
        self.bm25_index_ref: list[BM25Okapi | None] = [None]

    def workspace_docs(self, workspace_id: str | None) -> list[Document]:
        return [
            doc
            for doc in self.all_docs
            if workspace_matches(doc.metadata, workspace_id)
        ]

    def rebuild(self, tokenize: Callable[[str], list[str]]) -> None:
        self.doc_by_id.clear()
        self.doc_by_id.update(
            (doc.metadata["chunk_id"], doc)
            for doc in self.all_docs
            if doc.metadata.get("chunk_id")
        )
        self.existing_chunk_ids.clear()
        self.existing_chunk_ids.update(self.doc_by_id)
        self.bm25_corpus.clear()
        self.bm25_corpus.extend(tokenize(doc.page_content) for doc in self.all_docs)
        self.bm25_index_ref[0] = BM25Okapi(self.bm25_corpus) if self.bm25_corpus else None

    def extend_bm25(self, docs: list[Document], tokenize: Callable[[str], list[str]]) -> None:
        for doc in docs:
            self.bm25_corpus.append(tokenize(doc.page_content))
        self.bm25_index_ref[0] = BM25Okapi(self.bm25_corpus) if self.bm25_corpus else None

    def clear(self) -> None:
        self.all_docs.clear()
        self.doc_by_id.clear()
        self.existing_chunk_ids.clear()
        self.bm25_corpus.clear()
        self.bm25_index_ref[0] = None
