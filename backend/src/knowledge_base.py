"""Knowledge base ingestion, persistence, hybrid retrieval, and reranking support."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)
from typing import List, Optional, Tuple

import jieba
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

from config.settings import (
    CHROMA_PERSIST_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
    EMBEDDING_MODEL,
    ENABLE_CONTEXTUAL_RETRIEVAL,
    RRF_K,
    SCORE_THRESHOLD,
    SILICONFLOW_BASE_URL,
    TOP_K_RETRIEVAL,
    VECTOR_CANDIDATE_K,
    require_siliconflow_api_key,
)
from src.kb_models import (
    RetrievalResult,
    FusionScore,
    canonical_source_from_metadata,
    content_hash as compute_content_hash,
    chunk_id as _chunk_id,
    infer_source_type,
    normalize_source,
    document_chunk_id as _document_chunk_id,
)
from src.loaders import load_document
from src.api.models import HotspotEntry


def rrf_fuse(
    vector_ranked: list[tuple[str, float]],
    bm25_ranked: list[tuple[str, float]],
    limit: int,
    k: int = RRF_K,
) -> list[FusionScore]:
    """Fuse ranked vector and BM25 results with reciprocal rank fusion."""
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


class HotspotTracker:
    """Tracks document retrieval hit counts, persisted to JSON."""

    def __init__(self, hotspot_path: Path):
        self.hit_counter: dict[str, int] = {}
        self._hotspot_dirty = False
        self._hotspot_path = hotspot_path
        self._load_hotspots()

    def _load_hotspots(self):
        """Load hotspot counter from JSON file."""
        try:
            if self._hotspot_path.exists():
                with open(self._hotspot_path) as f:
                    self.hit_counter = json.load(f)
        except Exception as exc:
            logger.warning("热点计数加载失败: %s", exc)
            self.hit_counter = {}

    def _save_hotspots(self):
        """Persist hotspot counter to JSON file (no-op if not dirty)."""
        if not self._hotspot_dirty:
            return
        try:
            self._hotspot_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._hotspot_path, "w") as f:
                json.dump(self.hit_counter, f, ensure_ascii=False)
            self._hotspot_dirty = False
        except Exception as exc:
            logger.warning("热点计数持久化失败: %s", exc)

    def record_hit(self, chunk_id: str):
        """Increment hit count for a chunk."""
        self.hit_counter[chunk_id] = self.hit_counter.get(chunk_id, 0) + 1
        self._hotspot_dirty = True

    def get_hotspots(self, top_n: int, doc_by_id: dict[str, Document]) -> list[dict]:
        """Return top-N hotspots with chunk info."""
        sorted_chunks = sorted(
            self.hit_counter.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        result = []
        for chunk_id, hits in sorted_chunks[:top_n]:
            doc = doc_by_id.get(chunk_id)
            result.append({
                "chunk_id": chunk_id,
                "source": doc.metadata.get("source", "") if doc else "",
                "hits": hits,
                "content_preview": doc.page_content[:80] if doc else "",
            })
        return result

    def clear(self):
        """Reset all hotspot data."""
        self.hit_counter = {}
        self._hotspot_dirty = True
        self._save_hotspots()


class IngestionService:
    """Handles document loading, splitting, Chroma storage, and BM25 extension."""

    def __init__(
        self,
        vector_store: Chroma,
        all_docs: list[Document],
        doc_by_id: dict[str, Document],
        existing_chunk_ids: set[str],
        bm25_corpus: list[list[str]],
        bm25_index: list,
    ):
        self.vector_store = vector_store
        self._all_docs = all_docs
        self._doc_by_id = doc_by_id
        self._existing_chunk_ids = existing_chunk_ids
        self._bm25_corpus = bm25_corpus
        self._bm25_index = bm25_index  # Mutable list wrapping BM25Okapi | None
        self._loaded = False
        self._load_lock = threading.Lock()

    def _ensure_loaded(self):
        """Lazy-load all documents from Chroma on first need (double-checked locking)."""
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:
                return
            result = self.vector_store.get(include=["documents", "metadatas"])
            self._all_docs[:] = self._documents_from_chroma_result(result)
            self._rebuild_all()
            self._loaded = True

    def _rebuild_all(self):
        """Rebuild doc_by_id, existing_chunk_ids, and BM25 from all_docs."""
        self._doc_by_id.clear()
        self._doc_by_id.update(
            (doc.metadata["chunk_id"], doc)
            for doc in self._all_docs
            if doc.metadata.get("chunk_id")
        )
        self._existing_chunk_ids.clear()
        self._existing_chunk_ids.update(self._doc_by_id)
        self._bm25_corpus.clear()
        self._bm25_corpus.extend(self._tokenize(doc.page_content) for doc in self._all_docs)
        self._bm25_index[0] = BM25Okapi(self._bm25_corpus) if self._bm25_corpus else None

    def _extend_bm25(self, new_docs: list[Document]) -> None:
        """Incrementally extend BM25 with new documents."""
        for doc in new_docs:
            self._bm25_corpus.append(self._tokenize(doc.page_content))
        self._bm25_index[0] = BM25Okapi(self._bm25_corpus) if self._bm25_corpus else None

    @staticmethod
    def _documents_from_chroma_result(result: dict) -> list[Document]:
        """Convert Chroma get() output into LangChain documents."""
        contents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        ids = result.get("ids") or []

        docs = []
        for index, content in enumerate(contents):
            if not content:
                continue
            metadata = dict(metadatas[index] or {}) if index < len(metadatas) else {}
            source = canonical_source_from_metadata(metadata)
            content_hash = metadata.get("content_hash") or compute_content_hash(content)
            chunk_index = int(metadata.get("chunk_index", index))
            metadata["source"] = source
            metadata.setdefault("content_hash", content_hash)
            metadata.setdefault("chunk_index", chunk_index)
            existing_chunk_id = metadata.get("chunk_id")
            if existing_chunk_id:
                expected_prefix = f"{source}:{chunk_index}:"
                if not str(existing_chunk_id).startswith(expected_prefix):
                    metadata["legacy_chunk_id"] = str(existing_chunk_id)
                    metadata["chunk_id"] = _chunk_id(source, chunk_index, content_hash)
            else:
                metadata["chunk_id"] = _chunk_id(source, chunk_index, content_hash)
            metadata.setdefault("legacy_chroma_id", ids[index] if index < len(ids) else "")
            docs.append(Document(page_content=content, metadata=metadata))
        return docs

    @staticmethod
    def _vector_store_id(doc: Document) -> str:
        """Return the underlying Chroma row id for a document."""
        return str(
            doc.metadata.get("legacy_chroma_id")
            or doc.metadata.get("chunk_id")
            or ""
        )

    def _replace_old_chunks(self, source_name: str, new_docs: list[Document]) -> None:
        """Remove stale chunks for *source_name* that are not in *new_docs*."""
        self._ensure_loaded()
        src = normalize_source(source_name)
        old_ids = {
            doc.metadata["chunk_id"]
            for doc in self._all_docs
            if normalize_source(doc.metadata.get("source", "")) == src
        }
        if not old_ids:
            return
        new_ids = {
            d.metadata["chunk_id"]
            for d in self._prepare_splits(new_docs)
            if d.metadata.get("chunk_id")
        }
        stale_ids = old_ids - new_ids
        if not stale_ids:
            return
        stale_docs = [
            doc for doc in self._all_docs
            if doc.metadata.get("chunk_id") in stale_ids
        ]
        vector_ids = [self._vector_store_id(doc) for doc in stale_docs if self._vector_store_id(doc)]
        if vector_ids:
            self.vector_store.delete(ids=vector_ids)
        self._all_docs[:] = [
            doc for doc in self._all_docs
            if doc.metadata["chunk_id"] not in stale_ids
        ]
        self._rebuild_all()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize Chinese and mixed-language text for BM25."""
        return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]

    @staticmethod
    def _prepare_splits(docs: list[Document], version_mode: str = "replace", version_label: str = "") -> list[Document]:
        """Split documents and attach stable chunk metadata.

        Args:
            docs: Documents to split.
            version_mode: "replace" or "append". Append mode sets version metadata.
            version_label: Explicit version label (e.g. "v2"). Auto-generated if empty.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "！", "？", ""],
        )
        splits = splitter.split_documents(docs)
        per_source_counts: Counter[str] = Counter()
        ingested_at = datetime.now(UTC).isoformat()

        current_heading: dict[str, str] = {}

        for split in splits:
            source = normalize_source(split.metadata.get("source", "unknown"))
            chunk_index = per_source_counts[source]
            per_source_counts[source] += 1
            content_hash = compute_content_hash(split.page_content)

            first_line = split.page_content.split("\n")[0].strip()
            if first_line.startswith("## ") or first_line.startswith("# "):
                current_heading[source] = first_line.lstrip("#").strip()

            source_type = split.metadata.get("source_type") or infer_source_type(split.metadata.get("source", ""))
            meta = {
                "source": source,
                "source_type": source_type,
                "chunk_index": chunk_index,
                "content_hash": content_hash,
                "chunk_id": _chunk_id(source, chunk_index, content_hash),
                "section": current_heading.get(source, ""),
                "ingested_at": split.metadata.get("ingested_at", ingested_at),
            }
            if version_mode == "append":
                vl = version_label or f"v{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
                meta["version"] = vl
                meta["version_ingested_at"] = ingested_at
            split.metadata.update(meta)

        if ENABLE_CONTEXTUAL_RETRIEVAL:
            for split in splits:
                original = split.page_content
                section = split.metadata.get("section", "")
                source = split.metadata.get("source", "")
                ctx_parts = [f"本段属于文档「{source}」"]
                if section:
                    ctx_parts.append(f"章节：{section}")
                context_prefix = "，".join(ctx_parts)
                split.metadata["original_content"] = original
                split.page_content = f"{context_prefix}\n{original}"

        return splits

    def _process_documents(self, docs: list[Document], version_mode: str = "replace", version_label: str = "") -> int:
        """Split documents, store new chunks in Chroma, and extend BM25 incrementally."""
        self._ensure_loaded()
        splits = self._prepare_splits(docs, version_mode=version_mode, version_label=version_label)
        new_splits = [
            doc
            for doc in splits
            if doc.metadata["chunk_id"] not in self._existing_chunk_ids
        ]

        if not new_splits:
            return 0

        ids = [doc.metadata["chunk_id"] for doc in new_splits]
        self.vector_store.add_documents(new_splits, ids=ids)
        self._all_docs.extend(new_splits)
        for doc in new_splits:
            self._doc_by_id[doc.metadata["chunk_id"]] = doc
        self._existing_chunk_ids.update(doc.metadata["chunk_id"] for doc in new_splits)
        self._extend_bm25(new_splits)
        return len(new_splits)

    def load_preset_documents(self) -> int:
        """Load sample text documents from data/ without duplicating existing chunks."""
        txt_files = sorted(Path(DATA_DIR).glob("sample_*.txt"))
        total = 0
        for file_path in txt_files:
            total += self.ingest_file(str(file_path), source_name=file_path.name)
        return total

    def ingest_file(self, file_path: str, source_name: str | None = None, version_mode: str = "replace") -> int:
        """Ingest a file and return the number of new chunks."""
        docs = load_document(file_path, source_name=source_name)
        if source_name and version_mode == "skip":
            src_norm = normalize_source(source_name)
            existing = any(
                normalize_source(d.metadata.get("source", "")) == src_norm
                for d in self._all_docs
            )
            if existing:
                return 0

        if source_name and version_mode == "replace":
            self._replace_old_chunks(source_name, docs)

        vl = ""
        if version_mode == "append":
            existing_versions = set()
            src_norm = normalize_source(source_name or "")
            for d in self._all_docs:
                if normalize_source(d.metadata.get("source", "")) == src_norm:
                    v = d.metadata.get("version", "")
                    if v:
                        existing_versions.add(v)
            next_v = 1
            while f"v{next_v}" in existing_versions:
                next_v += 1
            vl = f"v{next_v}"

        new_count = self._process_documents(docs, version_mode=version_mode, version_label=vl)
        return new_count

    def ingest_url(self, url: str, version_mode: str = "replace") -> int:
        """Fetch a public URL and ingest its content."""
        from src.loaders import load_url

        docs = load_url(url)
        new_count = self._process_documents(docs)
        if version_mode == "replace":
            self._replace_old_chunks(url, docs)
        return new_count

    def add_document(self, file_path: str) -> int:
        """Compatibility wrapper for older UI code."""
        return self.ingest_file(file_path, source_name=Path(file_path).name)


class Retriever:
    """Handles hybrid search, neighbor chunk retrieval, full-text search, and source management."""

    def __init__(
        self,
        vector_store: Chroma,
        all_docs: list[Document],
        doc_by_id: dict[str, Document],
        existing_chunk_ids: set[str],
        bm25_corpus: list[list[str]],
        bm25_index: list,
        ingestion: IngestionService,
        hotspots: HotspotTracker,
    ):
        self.vector_store = vector_store
        self._all_docs = all_docs
        self._doc_by_id = doc_by_id
        self._existing_chunk_ids = existing_chunk_ids
        self._bm25_corpus = bm25_corpus
        self._bm25_index = bm25_index
        self._ingestion = ingestion
        self._hotspots = hotspots

    def hybrid_search(
        self,
        query: str,
        k: int = TOP_K_RETRIEVAL,
        *,
        score_threshold: float | None = SCORE_THRESHOLD,
        vector_candidate_k: int | None = None,
        filter: dict | None = None,
    ) -> list[RetrievalResult]:
        """Hybrid retrieval with vector search, candidate-set BM25, and RRF fusion."""
        self._ingestion._ensure_loaded()
        if vector_candidate_k is None:
            doc_count = len(self._existing_chunk_ids)
            min_candidates = 30
            max_candidates = 100
            candidate_k = min(max(min_candidates, int(doc_count * 0.3)), max_candidates)
        else:
            candidate_k = vector_candidate_k
        vector_results = self.vector_store.similarity_search_with_score(query, k=candidate_k, filter=filter)
        vector_ranked = [(_document_chunk_id(doc), float(score)) for doc, score in vector_results]
        vector_doc_map = {_document_chunk_id(doc): doc for doc, _score in vector_results}

        bm25_ranked: list[tuple[str, float]] = []
        bm25_index = self._bm25_index[0]
        if bm25_index and vector_doc_map:
            query_tokens = IngestionService._tokenize(query)
            candidate_docs = [
                self._doc_by_id[cid]
                for cid in vector_doc_map
                if cid in self._doc_by_id
            ]
            if candidate_docs:
                tokenized = [IngestionService._tokenize(doc.page_content) for doc in candidate_docs]
                candidate_bm25 = BM25Okapi(tokenized)
                bm25_scores = candidate_bm25.get_scores(query_tokens)
                bm25_ranked = [
                    (candidate_docs[i].metadata["chunk_id"], float(bm25_scores[i]))
                    for i in range(len(candidate_docs))
                    if bm25_scores[i] > 0
                ]
                bm25_ranked.sort(key=lambda x: x[1], reverse=True)
                bm25_ranked = bm25_ranked[: k * 2]

        fused = rrf_fuse(vector_ranked, bm25_ranked, limit=k)
        results = []
        for item in fused:
            if score_threshold is not None and item.score < score_threshold:
                continue
            doc = vector_doc_map.get(item.chunk_id) or self._doc_by_id.get(item.chunk_id)
            if doc is None:
                continue
            self._hotspots.record_hit(item.chunk_id)
            results.append(
                RetrievalResult(
                    chunk_id=item.chunk_id,
                    document=doc,
                    score=item.score,
                    vector_score=item.vector_score,
                    bm25_score=item.bm25_score,
                )
            )
        self._hotspots._save_hotspots()
        return results

    def get_neighbor_chunks(self, chunk_id: str, window: int = 1) -> list[Document]:
        """Return neighbor chunks around a given chunk_id from the same source."""
        self._ingestion._ensure_loaded()
        doc = self._doc_by_id.get(chunk_id)
        if doc is None:
            return []

        source = doc.metadata.get("source", "")
        chunk_index = doc.metadata.get("chunk_index")
        if not source or chunk_index is None:
            return [doc]

        same_source = sorted(
            [d for d in self._all_docs if d.metadata.get("source") == source],
            key=lambda d: d.metadata.get("chunk_index", 0),
        )
        if not same_source:
            return [doc]

        positions = {d.metadata.get("chunk_id"): i for i, d in enumerate(same_source)}
        pos = positions.get(chunk_id)
        if pos is None:
            return [doc]

        start = max(0, pos - window)
        end = min(len(same_source), pos + window + 1)
        return same_source[start:end]

    def search_content(self, query: str) -> list[Document]:
        """Full-text search across all in-memory documents."""
        self._ingestion._ensure_loaded()
        if not query or not self._all_docs:
            return []
        keywords = [kw.strip().lower() for kw in query.split() if kw.strip()]
        if not keywords:
            return []
        results = []
        for doc in self._all_docs:
            text = doc.page_content.lower()
            if any(kw in text for kw in keywords):
                results.append(doc)
        return results[:50]

    @property
    def document_count(self) -> int:
        """Return the number of indexed chunks."""
        return len(self._existing_chunk_ids)

    def source_counts(self) -> list[Tuple[str, int]]:
        """Return chunk counts by source file."""
        self._ingestion._ensure_loaded()
        counts: Counter[str] = Counter()
        for doc in self._all_docs:
            src = normalize_source(doc.metadata.get("source", "未知来源"))
            version = doc.metadata.get("version", "")
            key = f"{src} ({version})" if version else src
            counts[key] += 1
        return sorted(counts.items())

    def delete_source(self, source_name: str) -> int:
        """Delete all chunks belonging to a source file (and version if specified).

        Supports ``"doc.txt"`` (all versions) or ``"doc.txt (v2)"`` (single version).
        Returns the number of chunks removed.
        """
        self._ingestion._ensure_loaded()
        import re as _re
        version_filter = None
        m = _re.match(r"^(.+?)\s+\(v(\d+)\)$", source_name)
        if m:
            source_name = m.group(1).strip()
            version_filter = f"v{m.group(2)}"
        source_name = normalize_source(source_name)
        before = sum(
            1
            for doc in self._all_docs
            if normalize_source(doc.metadata.get("source", "")) == source_name
            and (version_filter is None or doc.metadata.get("version") == version_filter)
        )
        target_docs = [
            doc
            for doc in self._all_docs
            if normalize_source(doc.metadata.get("source", "")) == source_name
            and (version_filter is None or doc.metadata.get("version") == version_filter)
        ]
        vector_ids = [
            IngestionService._vector_store_id(doc)
            for doc in target_docs
            if IngestionService._vector_store_id(doc)
        ]
        if vector_ids:
            self.vector_store.delete(ids=vector_ids)

        self._all_docs[:] = [
            doc
            for doc in self._all_docs
            if normalize_source(doc.metadata.get("source", "")) != source_name
        ]
        self._ingestion._rebuild_all()
        return before

    def clear(self):
        """Clear all in-memory knowledge base state.  KnowledgeBase facade handles vector store."""
        self._all_docs.clear()
        self._doc_by_id.clear()
        self._existing_chunk_ids.clear()
        self._bm25_corpus.clear()
        self._bm25_index[0] = None
        self._ingestion._loaded = False
        self._hotspots.clear()


class KnowledgeBase:
    """Facade managing document ingestion, vector storage, BM25 indexing, and retrieval.

    Delegates to HotspotTracker, IngestionService, and Retriever under the hood.
    """

    def __init__(self):
        api_key = require_siliconflow_api_key()
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=api_key,
            openai_api_base=SILICONFLOW_BASE_URL,
        )
        self.vector_store = self._init_vector_store()

        # Shared mutable state for IngestionService + Retriever
        self.all_docs: List[Document] = []
        self.doc_by_id: dict[str, Document] = {}
        self.existing_chunk_ids: set[str] = set(self.vector_store.get(include=[])["ids"])

        # Wrapped in a list so IngestionService and Retriever share a mutable reference to BM25 index
        self._bm25_ref: list = [None]
        self._bm25_corpus_list: List[List[str]] = []

        self.hotspots = HotspotTracker(hotspot_path=Path(DATA_DIR) / "hotspots.json")

        self.ingestion = IngestionService(
            vector_store=self.vector_store,
            all_docs=self.all_docs,
            doc_by_id=self.doc_by_id,
            existing_chunk_ids=self.existing_chunk_ids,
            bm25_corpus=self._bm25_corpus_list,
            bm25_index=self._bm25_ref,
        )

        self.retriever = Retriever(
            vector_store=self.vector_store,
            all_docs=self.all_docs,
            doc_by_id=self.doc_by_id,
            existing_chunk_ids=self.existing_chunk_ids,
            bm25_corpus=self._bm25_corpus_list,
            bm25_index=self._bm25_ref,
            ingestion=self.ingestion,
            hotspots=self.hotspots,
        )

        # Write lock serializes concurrent upload/delete/clear operations.
        self._write_lock = threading.Lock()

    def _init_vector_store(self) -> Chroma:
        """Initialize the persistent vector store."""
        return Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=self.embeddings,
            collection_name="knowbase",
        )

    # -- Public delegation --

    def hybrid_search(
        self,
        query: str,
        k: int = TOP_K_RETRIEVAL,
        *,
        score_threshold: float | None = SCORE_THRESHOLD,
        vector_candidate_k: int | None = None,
        filter: dict | None = None,
    ) -> List[RetrievalResult]:
        return self.retriever.hybrid_search(
            query, k=k, score_threshold=score_threshold,
            vector_candidate_k=vector_candidate_k, filter=filter,
        )

    def get_neighbor_chunks(self, chunk_id: str, window: int = 1) -> List[Document]:
        return self.retriever.get_neighbor_chunks(chunk_id, window=window)

    def search_content(self, query: str) -> List[Document]:
        return self.retriever.search_content(query)

    def load_preset_documents(self) -> int:
        with self._write_lock:
            return self.ingestion.load_preset_documents()

    def ingest_file(self, file_path: str, source_name: str | None = None, version_mode: str = "replace") -> int:
        with self._write_lock:
            return self.ingestion.ingest_file(file_path, source_name=source_name, version_mode=version_mode)

    def ingest_url(self, url: str, version_mode: str = "replace") -> int:
        with self._write_lock:
            return self.ingestion.ingest_url(url, version_mode=version_mode)

    def add_document(self, file_path: str) -> int:
        with self._write_lock:
            return self.ingestion.add_document(file_path)

    def delete_source(self, source_name: str) -> int:
        with self._write_lock:
            return self.retriever.delete_source(source_name)

    def clear(self):
        with self._write_lock:
            self.vector_store.delete_collection()
            self.vector_store = self._init_vector_store()
            self.retriever.vector_store = self.vector_store
            self.ingestion.vector_store = self.vector_store
            self.retriever.clear()

    def get_hotspots(self, top_n: int = 50) -> List[dict]:
        self.retriever._ingestion._ensure_loaded()
        raw = self.hotspots.get_hotspots(top_n, self.doc_by_id)
        return [HotspotEntry(**entry) for entry in raw]

    @property
    def document_count(self) -> int:
        return self.retriever.document_count

    def source_counts(self) -> List[Tuple[str, int]]:
        return self.retriever.source_counts()
