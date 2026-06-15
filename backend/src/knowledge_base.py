"""Knowledge base ingestion, persistence, hybrid retrieval, and reranking support."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
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
from src.loaders import load_document


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


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _chunk_id(source: str, chunk_index: int, content_hash: str) -> str:
    return f"{Path(source).name}:{chunk_index}:{content_hash[:16]}"


def _infer_source_type(source: str) -> str:
    """Infer source_type from a source identifier."""
    if source.startswith("http://") or source.startswith("https://"):
        return "web_page"
    return "local_file"


def _document_chunk_id(doc: Document) -> str:
    chunk_id = doc.metadata.get("chunk_id")
    if chunk_id:
        return str(chunk_id)
    source = Path(doc.metadata.get("source", "unknown")).name
    chunk_index = int(doc.metadata.get("chunk_index", 0))
    content_hash = doc.metadata.get("content_hash") or _content_hash(doc.page_content)
    chunk_id = _chunk_id(source, chunk_index, content_hash)
    doc.metadata.setdefault("source", source)
    doc.metadata.setdefault("chunk_index", chunk_index)
    doc.metadata.setdefault("content_hash", content_hash)
    doc.metadata.setdefault("chunk_id", chunk_id)
    return chunk_id


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


class KnowledgeBase:
    """Manage document ingestion, vector storage, BM25 indexing, and retrieval.

    BM25 is built incrementally when new documents are added — no full
    corpus re-tokenization on each ingest.  Documents are loaded from Chroma
    lazily (on first retrieval or content browse), so startup is fast.
    """

    def __init__(self):
        api_key = require_siliconflow_api_key()
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=api_key,
            openai_api_base=SILICONFLOW_BASE_URL,
        )
        self.vector_store = self._init_vector_store()

        # Lazy-loaded state (populated on first retrieval / content access)
        self._loaded = False
        self.all_docs: List[Document] = []
        self.doc_by_id: dict[str, Document] = {}

        # Lightweight: only track existing chunk IDs for dedup (no document content)
        self.existing_chunk_ids: set[str] = set(self.vector_store.get(include=[])["ids"])

        # BM25 corpus — token lists maintained incrementally
        self._bm25_corpus: List[List[str]] = []
        self.bm25_index: Optional[BM25Okapi] = None

        # Retrieval hotspot tracking (chunk_id → hit count)
        self.hit_counter: dict[str, int] = {}
        self._hotspot_path = Path(DATA_DIR) / "hotspots.json"
        self._load_hotspots()

    def _ensure_loaded(self):
        """Lazy-load all documents from Chroma on first need."""
        if self._loaded:
            return
        result = self.vector_store.get(include=["documents", "metadatas"])
        self.all_docs = self._documents_from_chroma_result(result)
        self._rebuild_all()
        self._loaded = True

    def _load_hotspots(self):
        """Load hotspot counter from JSON file."""
        try:
            if self._hotspot_path.exists():
                with open(self._hotspot_path) as f:
                    self.hit_counter = json.load(f)
        except Exception:
            self.hit_counter = {}

    def _save_hotspots(self):
        """Persist hotspot counter to JSON file."""
        try:
            self._hotspot_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._hotspot_path, "w") as f:
                json.dump(self.hit_counter, f, ensure_ascii=False)
        except Exception:
            pass

    def _rebuild_all(self):
        """Build doc_by_id, existing_chunk_ids, and BM25 from all_docs (full rebuild).

        Used on first lazy load and after delete_source / clear.
        """
        self.doc_by_id = {
            doc.metadata["chunk_id"]: doc
            for doc in self.all_docs
            if doc.metadata.get("chunk_id")
        }
        self.existing_chunk_ids = set(self.doc_by_id)
        self._bm25_corpus = [self._tokenize(doc.page_content) for doc in self.all_docs]
        self.bm25_index = BM25Okapi(self._bm25_corpus) if self._bm25_corpus else None

    def _extend_bm25(self, new_docs: List[Document]) -> None:
        """Incrementally extend BM25 with new documents.

        Only tokenizes the new documents (O(len(new_docs))) instead of
        re-tokenizing the entire corpus.
        """
        for doc in new_docs:
            self._bm25_corpus.append(self._tokenize(doc.page_content))
        self.bm25_index = BM25Okapi(self._bm25_corpus) if self._bm25_corpus else None

    def _init_vector_store(self) -> Chroma:
        """Initialize the persistent vector store."""
        return Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=self.embeddings,
            collection_name="knowbase",
        )

    @staticmethod
    def _documents_from_chroma_result(result: dict) -> List[Document]:
        """Convert Chroma get() output into LangChain documents."""
        contents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        ids = result.get("ids") or []

        docs = []
        for index, content in enumerate(contents):
            if not content:
                continue
            metadata = dict(metadatas[index] or {}) if index < len(metadatas) else {}
            source = Path(metadata.get("source", "unknown")).name
            content_hash = metadata.get("content_hash") or _content_hash(content)
            chunk_index = int(metadata.get("chunk_index", index))
            metadata.setdefault("source", source)
            metadata.setdefault("content_hash", content_hash)
            metadata.setdefault("chunk_index", chunk_index)
            # Legacy Chroma rows used UUID ids and had no chunk_id metadata.
            # Always backfill the stable id so restarts do not re-ingest samples.
            metadata.setdefault("chunk_id", _chunk_id(source, chunk_index, content_hash))
            metadata.setdefault("legacy_chroma_id", ids[index] if index < len(ids) else "")
            docs.append(Document(page_content=content, metadata=metadata))
        return docs

    def load_preset_documents(self) -> int:
        """Load sample text documents from data/ without duplicating existing chunks."""
        txt_files = sorted(Path(DATA_DIR).glob("sample_*.txt"))
        total = 0
        for file_path in txt_files:
            total += self.ingest_file(str(file_path), source_name=file_path.name)
        return total

    def ingest_file(self, file_path: str, source_name: str | None = None) -> int:
        """Ingest a file and return the number of new chunks.

        Supported formats: .txt, .md, .pdf, .docx, .html (.htm).
        """
        docs = load_document(file_path, source_name=source_name)
        return self._process_documents(docs)

    def ingest_url(self, url: str) -> int:
        """Fetch a public URL and ingest its content.

        Returns the number of new chunks added.
        """
        from src.loaders import load_url

        docs = load_url(url)
        return self._process_documents(docs)

    def add_document(self, file_path: str) -> int:
        """Compatibility wrapper for older UI code."""
        return self.ingest_file(file_path, source_name=Path(file_path).name)

    @staticmethod
    def _prepare_splits(docs: List[Document]) -> List[Document]:
        """Split documents and attach stable chunk metadata."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "！", "？", ""],
        )
        splits = splitter.split_documents(docs)
        per_source_counts: Counter[str] = Counter()
        ingested_at = datetime.now(UTC).isoformat()

        # Track heading hierarchy for each source
        current_heading: dict[str, str] = {}

        for split in splits:
            source = Path(split.metadata.get("source", "unknown")).name
            chunk_index = per_source_counts[source]
            per_source_counts[source] += 1
            content_hash = _content_hash(split.page_content)

            # Detect and track heading for section chain
            first_line = split.page_content.split("\n")[0].strip()
            if first_line.startswith("## ") or first_line.startswith("# "):
                current_heading[source] = first_line.lstrip("#").strip()

            source_type = split.metadata.get("source_type") or _infer_source_type(split.metadata.get("source", ""))
            split.metadata.update(
                {
                    "source": source,
                    "source_type": source_type,
                    "chunk_index": chunk_index,
                    "content_hash": content_hash,
                    "chunk_id": _chunk_id(source, chunk_index, content_hash),
                    "section": current_heading.get(source, ""),
                    "ingested_at": split.metadata.get("ingested_at", ingested_at),
                }
            )

        # Contextual retrieval: prepend source/section context to page_content
        # so isolated chunks carry surrounding context for better embedding.
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

    def _process_documents(self, docs: List[Document]) -> int:
        """Split documents, store new chunks in Chroma, and extend BM25 incrementally."""
        splits = self._prepare_splits(docs)
        new_splits = [
            doc
            for doc in splits
            if doc.metadata["chunk_id"] not in self.existing_chunk_ids
        ]

        if not new_splits:
            return 0

        # Ensure full state is loaded before we append new docs
        self._ensure_loaded()

        ids = [doc.metadata["chunk_id"] for doc in new_splits]
        self.vector_store.add_documents(new_splits, ids=ids)
        self.all_docs.extend(new_splits)
        for doc in new_splits:
            self.doc_by_id[doc.metadata["chunk_id"]] = doc
        self.existing_chunk_ids.update(doc.metadata["chunk_id"] for doc in new_splits)
        self._extend_bm25(new_splits)
        return len(new_splits)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize Chinese and mixed-language text for BM25."""
        return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]

    def hybrid_search(
        self,
        query: str,
        k: int = TOP_K_RETRIEVAL,
        *,
        score_threshold: float | None = SCORE_THRESHOLD,
        vector_candidate_k: int | None = None,
        filter: dict | None = None,
    ) -> List[RetrievalResult]:
        """Hybrid retrieval with vector search, candidate-set BM25, and RRF fusion.

        1. Vector recall N candidates (default VECTOR_CANDIDATE_K)
        2. BM25 scores computed only on those N candidates (not full corpus)
        3. RRF fusion over both ranked lists
        4. Return top-k results
        """
        self._ensure_loaded()  # BM25 needs the full corpus loaded
        candidate_k = vector_candidate_k or VECTOR_CANDIDATE_K
        vector_results = self.vector_store.similarity_search_with_score(query, k=candidate_k, filter=filter)
        vector_ranked = [(_document_chunk_id(doc), float(score)) for doc, score in vector_results]
        vector_doc_map = {_document_chunk_id(doc): doc for doc, _score in vector_results}

        bm25_ranked: list[tuple[str, float]] = []
        if self.bm25_index and vector_doc_map:
            query_tokens = self._tokenize(query)
            # Build candidate BM25 index from vector candidates
            candidate_docs = [
                self.doc_by_id[cid]
                for cid in vector_doc_map
                if cid in self.doc_by_id
            ]
            if candidate_docs:
                tokenized = [self._tokenize(doc.page_content) for doc in candidate_docs]
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
            doc = vector_doc_map.get(item.chunk_id) or self.doc_by_id.get(item.chunk_id)
            if doc is None:
                continue
            # Count each retrieval hit for hotspot analysis
            self.hit_counter[item.chunk_id] = self.hit_counter.get(item.chunk_id, 0) + 1
            self._save_hotspots()
            results.append(
                RetrievalResult(
                    chunk_id=item.chunk_id,
                    document=doc,
                    score=item.score,
                    vector_score=item.vector_score,
                    bm25_score=item.bm25_score,
                )
            )
        return results

    def get_neighbor_chunks(self, chunk_id: str, window: int = 1) -> list[Document]:
        """Return neighbor chunks around a given chunk_id from the same source.

        ``window`` controls how many neighbors on each side to include
        (default 1 = one before + one after).  Returns an ordered list with the
        original chunk in the middle when possible.
        """
        self._ensure_loaded()
        doc = self.doc_by_id.get(chunk_id)
        if doc is None:
            return []

        source = doc.metadata.get("source", "")
        chunk_index = doc.metadata.get("chunk_index")
        if not source or chunk_index is None:
            return [doc]

        # Collect all chunks from the same source, ordered by chunk_index
        same_source = sorted(
            [d for d in self.all_docs if d.metadata.get("source") == source],
            key=lambda d: d.metadata.get("chunk_index", 0),
        )
        if not same_source:
            return [doc]

        # Find position of the original chunk
        positions = {d.metadata.get("chunk_id"): i for i, d in enumerate(same_source)}
        pos = positions.get(chunk_id)
        if pos is None:
            return [doc]

        start = max(0, pos - window)
        end = min(len(same_source), pos + window + 1)
        return same_source[start:end]

    @property
    def document_count(self) -> int:
        """Return the number of indexed chunks."""
        return len(self.existing_chunk_ids)

    def source_counts(self) -> List[Tuple[str, int]]:
        """Return chunk counts by source file."""
        self._ensure_loaded()
        counts = Counter(
            Path(doc.metadata.get("source", "未知来源")).name
            for doc in self.all_docs
        )
        return sorted(counts.items())

    def get_hotspots(self, top_n: int = 50) -> list[dict]:
        """Return chunks sorted by retrieval hit count, for hotspot visualization."""
        self._ensure_loaded()
        sorted_chunks = sorted(
            self.hit_counter.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        result = []
        for chunk_id, hits in sorted_chunks[:top_n]:
            doc = self.doc_by_id.get(chunk_id)
            result.append({
                "chunk_id": chunk_id,
                "source": doc.metadata.get("source", "") if doc else "",
                "hits": hits,
                "content_preview": doc.page_content[:80] if doc else "",
            })
        return result

    def delete_source(self, source_name: str) -> int:
        """Delete all chunks belonging to a source file.

        Returns the number of chunks removed.
        """
        self._ensure_loaded()
        source_name = Path(source_name).name
        before = sum(
            1
            for doc in self.all_docs
            if Path(doc.metadata.get("source", "")).name == source_name
        )

        # Chroma: delete by metadata filter
        self.vector_store.delete(filter={"source": source_name})

        # In-memory: rebuild from remaining chunks
        self.all_docs = [
            doc
            for doc in self.all_docs
            if Path(doc.metadata.get("source", "")).name != source_name
        ]
        self._rebuild_all()
        return before

    def clear(self):
        """Clear all persisted and in-memory knowledge base state."""
        self.vector_store.delete_collection()
        self.vector_store = self._init_vector_store()
        self._loaded = False
        self.all_docs = []
        self.doc_by_id = {}
        self.existing_chunk_ids = set()
        self._bm25_corpus = []
        self.bm25_index = None
        self.hit_counter = {}
        self._save_hotspots()

    def search_content(self, query: str) -> List[Document]:
        """Full-text search across all in-memory documents.

        Returns documents where any query keyword appears in the content.
        Useful for the knowledge base browser UI.
        """
        self._ensure_loaded()
        if not query or not self.all_docs:
            return []
        keywords = [kw.strip().lower() for kw in query.split() if kw.strip()]
        if not keywords:
            return []
        results = []
        for doc in self.all_docs:
            text = doc.page_content.lower()
            if any(kw in text for kw in keywords):
                results.append(doc)
        return results[:50]
