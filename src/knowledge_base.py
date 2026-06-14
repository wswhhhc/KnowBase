"""Knowledge base ingestion, persistence, hybrid retrieval, and reranking support."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

import jieba
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
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
    RRF_K,
    SCORE_THRESHOLD,
    SILICONFLOW_BASE_URL,
    TOP_K_RETRIEVAL,
    require_siliconflow_api_key,
)


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
    """Manage document ingestion, vector storage, BM25 indexing, and retrieval."""

    def __init__(self):
        api_key = require_siliconflow_api_key()
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=api_key,
            openai_api_base=SILICONFLOW_BASE_URL,
        )
        self.vector_store = self._init_vector_store()
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_docs: List[Document] = []
        self.all_docs: List[Document] = self._load_existing_documents()
        self.doc_by_id: dict[str, Document] = {}
        self.existing_chunk_ids: set[str] = set()
        self._rebuild_indexes()

    def _init_vector_store(self) -> Chroma:
        """Initialize the persistent vector store."""
        return Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=self.embeddings,
            collection_name="knowbase",
        )

    def _load_existing_documents(self) -> List[Document]:
        """Restore existing chunks from Chroma for UI counts and BM25."""
        result = self.vector_store.get(include=["documents", "metadatas"])
        return self._documents_from_chroma_result(result)

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
        """Ingest a single .txt or .md file and return the number of new chunks."""
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext not in {".txt", ".md"}:
            raise ValueError(f"不支持的文件格式：{ext}")

        display_source = Path(source_name or path.name).name
        loader = TextLoader(str(path), encoding="utf-8")
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = display_source
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
            separators=["\n## ", "\n### ", "\n\n", "\n", "。", ""],
        )
        splits = splitter.split_documents(docs)
        per_source_counts: Counter[str] = Counter()
        ingested_at = datetime.now(UTC).isoformat()

        for split in splits:
            source = Path(split.metadata.get("source", "unknown")).name
            chunk_index = per_source_counts[source]
            per_source_counts[source] += 1
            content_hash = _content_hash(split.page_content)
            split.metadata.update(
                {
                    "source": source,
                    "chunk_index": chunk_index,
                    "content_hash": content_hash,
                    "chunk_id": _chunk_id(source, chunk_index, content_hash),
                    "ingested_at": split.metadata.get("ingested_at", ingested_at),
                }
            )

        return splits

    def _process_documents(self, docs: List[Document]) -> int:
        """Split documents, store new chunks in Chroma, and rebuild lexical indexes."""
        splits = self._prepare_splits(docs)
        new_splits = [
            doc
            for doc in splits
            if doc.metadata["chunk_id"] not in self.existing_chunk_ids
        ]

        if not new_splits:
            return 0

        ids = [doc.metadata["chunk_id"] for doc in new_splits]
        self.vector_store.add_documents(new_splits, ids=ids)
        self.all_docs.extend(new_splits)
        self._rebuild_indexes()
        return len(new_splits)

    def _rebuild_indexes(self) -> None:
        """Rebuild BM25 and id lookup state."""
        self.doc_by_id = {
            doc.metadata["chunk_id"]: doc
            for doc in self.all_docs
            if doc.metadata.get("chunk_id")
        }
        self.existing_chunk_ids = set(self.doc_by_id)
        self.bm25_docs = list(self.doc_by_id.values())
        if not self.bm25_docs:
            self.bm25_index = None
            return

        tokenized = [self._tokenize(doc.page_content) for doc in self.bm25_docs]
        self.bm25_index = BM25Okapi(tokenized)

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
    ) -> List[RetrievalResult]:
        """Hybrid retrieval with vector search, BM25, and RRF fusion."""
        vector_results = self.vector_store.similarity_search_with_score(query, k=k * 2)
        vector_ranked = [(_document_chunk_id(doc), score) for doc, score in vector_results]
        vector_doc_map = {_document_chunk_id(doc): doc for doc, _score in vector_results}

        bm25_ranked: list[tuple[str, float]] = []
        if self.bm25_index:
            query_tokens = self._tokenize(query)
            bm25_scores = self.bm25_index.get_scores(query_tokens)
            bm25_ranked = [
                (doc.metadata["chunk_id"], float(score))
                for doc, score in sorted(
                    zip(self.bm25_docs, bm25_scores),
                    key=lambda item: item[1],
                    reverse=True,
                )[: k * 2]
                if score > 0
            ]

        fused = rrf_fuse(vector_ranked, bm25_ranked, limit=k)
        results = []
        for item in fused:
            if score_threshold is not None and item.score < score_threshold:
                continue
            doc = vector_doc_map.get(item.chunk_id) or self.doc_by_id.get(item.chunk_id)
            if doc is None:
                continue
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

    @property
    def document_count(self) -> int:
        """Return the number of indexed chunks."""
        return len(self.all_docs)

    def source_counts(self) -> List[Tuple[str, int]]:
        """Return chunk counts by source file."""
        counts = Counter(
            Path(doc.metadata.get("source", "未知来源")).name
            for doc in self.all_docs
        )
        return sorted(counts.items())

    def clear(self):
        """Clear all persisted and in-memory knowledge base state."""
        self.vector_store.delete_collection()
        self.vector_store = self._init_vector_store()
        self.bm25_index = None
        self.bm25_docs = []
        self.all_docs = []
        self.doc_by_id = {}
        self.existing_chunk_ids = set()
