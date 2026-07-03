"""Hybrid retrieval and neighbor expansion for the knowledge base."""

from __future__ import annotations

from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from src.config.settings import RRF_K, SCORE_THRESHOLD, TOP_K_RETRIEVAL
from src.rag.kb_hotspots import HotspotTracker
from src.rag.kb_ingestion import IngestionService
from src.rag.kb_state import KnowledgeBaseState, search_keywords, workspace_matches
from src.rag.models import FusionScore, RetrievalResult, document_chunk_id, normalize_workspace_id


def rrf_fuse(
    vector_ranked: list[tuple[str, float]],
    bm25_ranked: list[tuple[str, float]],
    limit: int,
    k: int = RRF_K,
) -> list[FusionScore]:
    scores: dict[str, float] = {}
    vector_scores = dict(vector_ranked)
    bm25_scores = dict(bm25_ranked)

    for ranked in (vector_ranked, bm25_ranked):
        for rank, (chunk_id, _raw_score) in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return [
        FusionScore(
            chunk_id=chunk_id,
            score=score,
            vector_score=vector_scores.get(chunk_id),
            bm25_score=bm25_scores.get(chunk_id),
        )
        for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


class Retriever:
    """Handles hybrid search, debug retrieval breakdown, and chunk neighborhood lookup."""

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

    def _candidate_k(self, requested: int | None, *, workspace_id: str | None, minimum: int = 0) -> int:
        if requested is not None:
            return requested
        if self._ingestion._loaded:
            doc_count = len(self._workspace_docs(workspace_id))
        else:
            doc_count = len(self._existing_chunk_ids)
        base = min(max(30, int(doc_count * 0.3)), 100)
        return max(minimum, base)

    def _vector_results(
        self,
        query: str,
        *,
        candidate_k: int,
        filter: dict[str, Any] | None,
        workspace_id: str | None,
    ) -> list[tuple[Document, float]]:
        vector_filter = dict(filter or {})
        if workspace_id is not None:
            vector_filter["workspace_id"] = normalize_workspace_id(workspace_id)
        vector_results = self.vector_store.similarity_search_with_score(
            query,
            k=candidate_k,
            filter=vector_filter or None,
        )
        if workspace_id is None:
            return vector_results
        return [
            (doc, score)
            for doc, score in vector_results
            if workspace_matches(doc.metadata, workspace_id)
        ]

    def _candidate_bm25_rankings(
        self,
        query: str,
        vector_doc_map: dict[str, Document],
        *,
        limit: int,
    ) -> list[tuple[str, float]]:
        if not vector_doc_map:
            return []
        query_tokens = IngestionService._tokenize(query)
        candidate_docs = [
            vector_doc_map[chunk_id]
            for chunk_id in vector_doc_map
        ]
        if not candidate_docs:
            return []

        tokenized = [IngestionService._tokenize(doc.page_content) for doc in candidate_docs]
        candidate_bm25 = BM25Okapi(tokenized)
        bm25_scores = candidate_bm25.get_scores(query_tokens)
        ranked = [
            (candidate_docs[index].metadata["chunk_id"], float(bm25_scores[index]))
            for index in range(len(candidate_docs))
            if bm25_scores[index] > 0
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:limit]

    def _workspace_bm25_rankings(self, query: str, workspace_id: str | None) -> list[tuple[str, float]]:
        self._ingestion._ensure_bm25_loaded()
        query_tokens = IngestionService._tokenize(query)
        if not query_tokens:
            return []

        scoped_docs = self._workspace_docs(workspace_id)
        if not scoped_docs:
            return []

        scoped_bm25 = BM25Okapi([IngestionService._tokenize(doc.page_content) for doc in scoped_docs])
        raw_scores = scoped_bm25.get_scores(query_tokens)
        ranked = [
            (scoped_docs[index].metadata["chunk_id"], float(raw_scores[index]))
            for index in range(len(scoped_docs))
            if raw_scores[index] > 0
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    @staticmethod
    def _result_from_maps(
        chunk_id: str,
        score: float,
        *,
        vector_doc_map: dict[str, Document],
        doc_by_id: dict[str, Document],
        vector_score: float | None = None,
        bm25_score: float | None = None,
    ) -> RetrievalResult | None:
        doc = vector_doc_map.get(chunk_id) or doc_by_id.get(chunk_id)
        if doc is None:
            return None
        return RetrievalResult(
            chunk_id=chunk_id,
            document=doc,
            score=score,
            vector_score=vector_score,
            bm25_score=bm25_score,
        )

    def hybrid_search(
        self,
        query: str,
        k: int = TOP_K_RETRIEVAL,
        *,
        score_threshold: float | None = SCORE_THRESHOLD,
        vector_candidate_k: int | None = None,
        filter: dict | None = None,
        workspace_id: str | None = None,
    ) -> list[RetrievalResult]:
        candidate_k = self._candidate_k(vector_candidate_k, workspace_id=workspace_id)
        vector_results = self._vector_results(
            query,
            candidate_k=candidate_k,
            filter=filter,
            workspace_id=workspace_id,
        )
        vector_ranked = [(document_chunk_id(doc), float(score)) for doc, score in vector_results]
        vector_doc_map = {document_chunk_id(doc): doc for doc, _score in vector_results}
        bm25_ranked = self._candidate_bm25_rankings(query, vector_doc_map, limit=k * 2)

        results = []
        for item in rrf_fuse(vector_ranked, bm25_ranked, limit=k):
            if score_threshold is not None and item.score < score_threshold:
                continue
            result = self._result_from_maps(
                item.chunk_id,
                item.score,
                vector_doc_map=vector_doc_map,
                doc_by_id={},
                vector_score=item.vector_score,
                bm25_score=item.bm25_score,
            )
            if result is None:
                continue
            self._hotspots.record_hit(item.chunk_id)
            results.append(result)
        self._hotspots._save_hotspots()
        return results

    def debug_search_breakdown(
        self,
        query: str,
        k: int = TOP_K_RETRIEVAL,
        *,
        filter: dict | None = None,
        vector_candidate_k: int | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, list[RetrievalResult]]:
        self._ingestion._ensure_loaded()
        candidate_k = self._candidate_k(
            vector_candidate_k,
            workspace_id=workspace_id,
            minimum=k * 3,
        )
        vector_results = self._vector_results(
            query,
            candidate_k=candidate_k,
            filter=filter,
            workspace_id=workspace_id,
        )
        vector_ranked = [(document_chunk_id(doc), float(score)) for doc, score in vector_results]
        vector_doc_map = {document_chunk_id(doc): doc for doc, _score in vector_results}
        bm25_ranked = self._workspace_bm25_rankings(query, workspace_id)
        fused = rrf_fuse(vector_ranked, bm25_ranked, limit=candidate_k)

        vector_top = [
            result
            for chunk_id, score in vector_ranked[:k]
            if (
                result := self._result_from_maps(
                    chunk_id,
                    score,
                    vector_doc_map=vector_doc_map,
                    doc_by_id=self._doc_by_id,
                    vector_score=score,
                )
            ) is not None
        ]
        bm25_top = [
            result
            for chunk_id, score in bm25_ranked[:k]
            if (
                result := self._result_from_maps(
                    chunk_id,
                    score,
                    vector_doc_map=vector_doc_map,
                    doc_by_id=self._doc_by_id,
                    bm25_score=score,
                )
            ) is not None
        ]
        fused_top = [
            result
            for item in fused[:k]
            if (
                result := self._result_from_maps(
                    item.chunk_id,
                    item.score,
                    vector_doc_map=vector_doc_map,
                    doc_by_id=self._doc_by_id,
                    vector_score=item.vector_score,
                    bm25_score=item.bm25_score,
                )
            ) is not None
        ]
        return {
            "vector_results": vector_top,
            "bm25_results": bm25_top,
            "fused_results": fused_top,
        }

    def get_neighbor_chunks(self, chunk_id: str, window: int = 1, workspace_id: str | None = None) -> list[Document]:
        self._ingestion._ensure_loaded()
        doc = self._doc_by_id.get(chunk_id)
        if doc is None:
            return []
        if workspace_id is not None and not workspace_matches(doc.metadata, workspace_id):
            return []

        source = doc.metadata.get("source", "")
        chunk_index = doc.metadata.get("chunk_index")
        if not source or chunk_index is None:
            return [doc]

        same_source = sorted(
            [
                candidate
                for candidate in self._all_docs
                if candidate.metadata.get("source") == source
                and workspace_matches(candidate.metadata, workspace_id)
            ],
            key=lambda candidate: candidate.metadata.get("chunk_index", 0),
        )
        if not same_source:
            return [doc]

        positions = {candidate.metadata.get("chunk_id"): index for index, candidate in enumerate(same_source)}
        pos = positions.get(chunk_id)
        if pos is None:
            return [doc]

        start = max(0, pos - window)
        end = min(len(same_source), pos + window + 1)
        return same_source[start:end]

    def search_content(self, query: str, workspace_id: str | None = None) -> list[Document]:
        scoped_docs = self._workspace_docs(workspace_id)
        keywords = search_keywords(query)
        if not keywords or not scoped_docs:
            return []

        results = []
        for doc in scoped_docs:
            text = doc.page_content.lower()
            if any(keyword in text for keyword in keywords):
                results.append(doc)
        return results[:50]

    @property
    def document_count(self) -> int:
        return len(self._existing_chunk_ids)
