"""Workspace-aware catalog, analytics, and maintenance operations for the KB."""

from __future__ import annotations

from collections import Counter

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.rag.kb_hotspots import HotspotTracker
from src.rag.kb_ingestion import IngestionService
from src.rag.kb_state import KnowledgeBaseState, parse_versioned_source_label, search_keywords, workspace_matches
from src.rag.models import HotspotEntry, KBChunk, normalize_source


def _doc_matches_source(doc: Document, source_name: str, version: str | None) -> bool:
    return (
        normalize_source(doc.metadata.get("source", "")) == source_name
        and (version is None or doc.metadata.get("version") == version)
    )


def _doc_to_chunk(doc: Document) -> KBChunk:
    return KBChunk(
        source=doc.metadata.get("source", ""),
        chunk_index=doc.metadata.get("chunk_index", 0),
        chunk_id=doc.metadata.get("chunk_id", ""),
        page=doc.metadata.get("page"),
        content=doc.page_content,
        original_content=doc.metadata.get("original_content"),
        section=doc.metadata.get("section"),
    )


class CatalogService:
    """Read-heavy metadata operations and workspace-scoped maintenance helpers."""

    def __init__(
        self,
        vector_store: Chroma,
        state: KnowledgeBaseState,
        ingestion: IngestionService,
        hotspots: HotspotTracker,
    ):
        self.vector_store = vector_store
        self._state = state
        self._ingestion = ingestion
        self._hotspots = hotspots
        self._all_docs = state.all_docs
        self._doc_by_id = state.doc_by_id
        self._existing_chunk_ids = state.existing_chunk_ids
        self._bm25_corpus = state.bm25_corpus
        self._bm25_index = state.bm25_index_ref

    def _workspace_docs(self, workspace_id: str | None) -> list[Document]:
        self._ingestion._ensure_loaded()
        return self._state.workspace_docs(workspace_id)

    def source_counts(self, workspace_id: str | None = None) -> list[tuple[str, int]]:
        counts: Counter[str] = Counter()
        for doc in self._workspace_docs(workspace_id):
            source = normalize_source(doc.metadata.get("source", "未知来源"))
            version = doc.metadata.get("version", "")
            counts[f"{source} ({version})" if version else source] += 1
        return sorted(counts.items())

    def get_hotspots(self, top_n: int = 50, workspace_id: str | None = None) -> list[HotspotEntry]:
        scoped_docs = {
            chunk_id: doc
            for chunk_id, doc in self._doc_by_id.items()
            if workspace_matches(doc.metadata, workspace_id)
        }
        doc_map = scoped_docs if workspace_id is not None else self._doc_by_id
        return [
            HotspotEntry(**entry)
            for entry in self._hotspots.get_hotspots(top_n, doc_map)
        ]

    def get_chunk_by_id(self, chunk_id: str, workspace_id: str | None = None) -> KBChunk | None:
        self._ingestion._ensure_loaded()
        doc = self._doc_by_id.get(chunk_id)
        if doc is None:
            return None
        if workspace_id is not None and not workspace_matches(doc.metadata, workspace_id):
            return None
        return _doc_to_chunk(doc)

    def document_count_for_workspace(self, workspace_id: str = "") -> int:
        return len(self._workspace_docs(workspace_id))

    def stats(self, workspace_id: str = "") -> dict[str, int]:
        docs = self._workspace_docs(workspace_id)
        return {
            "chunk_count": len(docs),
            "source_count": len(self.source_counts(workspace_id)),
            "total_chars": sum(len(doc.page_content) for doc in docs),
        }

    def list_chunks(
        self,
        *,
        workspace_id: str = "",
        source: str = "",
        search: str = "",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[KBChunk]]:
        docs = self._workspace_docs(workspace_id)
        if source:
            normalized_source, version = parse_versioned_source_label(source)
            docs = [
                doc
                for doc in docs
                if _doc_matches_source(doc, normalized_source, version)
            ]
        if search:
            keywords = search_keywords(search)
            docs = [
                doc
                for doc in docs
                if any(keyword in doc.page_content.lower() for keyword in keywords)
            ]
        total = len(docs)
        return total, [_doc_to_chunk(doc) for doc in docs[skip: skip + limit]]

    def delete_source(self, source_name: str, workspace_id: str | None = None) -> int:
        self._ingestion._ensure_loaded()
        normalized_source, version = parse_versioned_source_label(source_name)
        target_docs = [
            doc
            for doc in self._all_docs
            if _doc_matches_source(doc, normalized_source, version)
            and workspace_matches(doc.metadata, workspace_id)
        ]
        vector_ids = [
            IngestionService._vector_store_id(doc)
            for doc in target_docs
            if IngestionService._vector_store_id(doc)
        ]
        if vector_ids:
            self.vector_store.delete(ids=vector_ids)
        removed = len(target_docs)
        if removed == 0:
            return 0
        removed_ids = {doc.metadata["chunk_id"] for doc in target_docs}
        self._all_docs[:] = [
            doc
            for doc in self._all_docs
            if doc.metadata.get("chunk_id") not in removed_ids
        ]
        self._ingestion._rebuild_all()
        return removed

    def clear_workspace(self, workspace_id: str | None = None) -> int:
        docs = self._workspace_docs(workspace_id)
        vector_ids = [
            IngestionService._vector_store_id(doc)
            for doc in docs
            if IngestionService._vector_store_id(doc)
        ]
        if vector_ids:
            self.vector_store.delete(ids=vector_ids)
        removed = len(docs)
        if removed == 0:
            return 0
        self._all_docs[:] = [
            doc
            for doc in self._all_docs
            if not workspace_matches(doc.metadata, workspace_id)
        ]
        self._ingestion._rebuild_all()
        return removed

    def clear(self) -> None:
        self._state.clear()
        self._ingestion._loaded = False
        self._hotspots.clear()
