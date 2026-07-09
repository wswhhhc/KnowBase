"""Public knowledge-base facade with stable APIs and clearer internal boundaries."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import threading
import hashlib
from typing import TypeVar

from chromadb.api.shared_system_client import SharedSystemClient
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from src.config.constants import CHROMA_PERSIST_DIR, DATA_DIR, EMBEDDING_MODEL, SCORE_THRESHOLD, SILICONFLOW_BASE_URL, TOP_K_RETRIEVAL
from src.config.runtime_overrides import get_runtime_setting, require_siliconflow_api_key
from src.config.settings import settings
from src.rag.kb_catalog import CatalogService
from src.rag.kb_hotspots import HotspotTracker
from src.rag.kb_ingestion import IngestionService
from src.rag.kb_retrieval import Retriever, rrf_fuse
from src.rag.kb_state import KnowledgeBaseState, workspace_matches
from src.rag.loaders import load_document
from src.rag.models import HotspotEntry, KBChunk, RetrievalResult


logger = logging.getLogger(__name__)


_RECOVERABLE_VECTOR_INDEX_ERROR_MARKERS = (
    "Error finding id",
)
_T = TypeVar("_T")


class EmbeddingIndexMismatchError(ValueError):
    """Raised when the configured embedding model does not match persisted vectors."""


class DeterministicTestEmbeddings:
    """Small local embeddings used only by the explicit E2E fake-AI mode."""

    dimension = 1024

    def _embed(self, text: str) -> list[float]:
        values: list[float] = []
        seed = text.encode("utf-8")
        counter = 0
        while len(values) < self.dimension:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            values.extend(((byte / 255.0) * 2.0) - 1.0 for byte in digest)
            counter += 1
        return values[: self.dimension]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def _load_document(file_path: str, source_name: str | None = None) -> list[Document]:
    return load_document(file_path, source_name=source_name)


def _load_url(url: str) -> list[Document]:
    from src.rag.loaders import load_url

    return load_url(url)


class KnowledgeBase:
    """Facade managing ingestion, retrieval, and catalog operations for the KB."""

    def __init__(self, *, require_embeddings: bool = True):
        self.embedding_model = get_runtime_setting("embedding_model", EMBEDDING_MODEL)
        self._index_meta_path = Path(DATA_DIR) / "vector_store_meta.json"
        self._embedding_mismatch_error: str | None = None
        self.embeddings = None
        if require_embeddings:
            self.embeddings = self._create_embeddings()
        self.vector_store = self._init_vector_store()

        self.state = KnowledgeBaseState(initial_chunk_ids=self.vector_store.get(include=[])["ids"])
        self.all_docs = self.state.all_docs
        self.doc_by_id = self.state.doc_by_id
        self.existing_chunk_ids = self.state.existing_chunk_ids
        self._bm25_ref = self.state.bm25_index_ref
        self._bm25_corpus_list = self.state.bm25_corpus
        self._refresh_index_metadata_state()

        self.hotspots = HotspotTracker(hotspot_path=Path(DATA_DIR) / "hotspots.json")
        self.ingestion = IngestionService(
            vector_store=self.vector_store,
            state=self.state,
            document_loader=_load_document,
            url_loader=_load_url,
        )
        self.retriever = Retriever(
            vector_store=self.vector_store,
            state=self.state,
            ingestion=self.ingestion,
            hotspots=self.hotspots,
        )
        self.catalog = CatalogService(
            vector_store=self.vector_store,
            state=self.state,
            ingestion=self.ingestion,
            hotspots=self.hotspots,
        )

        self._write_lock = threading.Lock()

    @staticmethod
    def _is_recoverable_vector_index_error(exc: Exception) -> bool:
        message = str(exc)
        return any(marker in message for marker in _RECOVERABLE_VECTOR_INDEX_ERROR_MARKERS)

    def refresh_from_persisted_store(self) -> None:
        """Reopen Chroma and discard lazy-loaded in-memory state.

        Local self-hosted runs use a separate RQ worker process for ingestion.
        Chroma's long-lived API process handle can become stale after that
        external writer mutates the persisted index, which may surface as
        "Error finding id" during vector search. Reopening the store is safe
        for read paths and keeps the API process in sync with disk.
        """
        with self._write_lock:
            SharedSystemClient.clear_system_cache()
            self.vector_store = self._init_vector_store()
            self.state.clear()
            self.state.existing_chunk_ids.update(self.vector_store.get(include=[]).get("ids") or [])
            self.ingestion.vector_store = self.vector_store
            self.retriever.vector_store = self.vector_store
            self.catalog.vector_store = self.vector_store
            self._refresh_index_metadata_state()

    def _retry_after_vector_refresh(self, operation: Callable[[], _T], *, operation_name: str) -> _T:
        try:
            return operation()
        except Exception as exc:
            if not self._is_recoverable_vector_index_error(exc):
                raise
            logger.warning(
                "Chroma vector index handle was stale during %s; reopening persisted store and retrying once: %s",
                operation_name,
                exc,
            )
            self.refresh_from_persisted_store()
            return operation()

    def _create_embeddings(self):
        if settings.e2e_fake_ai:
            return DeterministicTestEmbeddings()

        api_key = require_siliconflow_api_key()
        return OpenAIEmbeddings(
            model=self.embedding_model,
            openai_api_key=api_key,
            openai_api_base=get_runtime_setting("siliconflow_base_url", SILICONFLOW_BASE_URL),
        )

    def _read_index_metadata(self) -> dict:
        try:
            if self._index_meta_path.exists():
                with open(self._index_meta_path, encoding="utf-8") as file:
                    return json.load(file)
        except Exception as exc:
            logger.warning("向量索引元数据读取失败: %s", exc)
        return {}

    def _write_index_metadata(self) -> None:
        try:
            self._index_meta_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._index_meta_path, "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "embedding_model": self.embedding_model,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as exc:
            logger.warning("向量索引元数据写入失败: %s", exc)

    def _refresh_index_metadata_state(self) -> None:
        metadata = self._read_index_metadata()
        stored_model = metadata.get("embedding_model")

        if self.existing_chunk_ids:
            if not stored_model:
                self._write_index_metadata()
                self._embedding_mismatch_error = None
                return
            if stored_model != self.embedding_model:
                self._embedding_mismatch_error = (
                    "当前 embedding 模型与现有向量索引不一致。"
                    "请先清空知识库并重新导入文档，再继续检索或上传。"
                )
                return
            self._embedding_mismatch_error = None
            return

        self._embedding_mismatch_error = None
        self._write_index_metadata()

    def _ensure_embedding_compatible(self) -> None:
        if self._embedding_mismatch_error:
            raise EmbeddingIndexMismatchError(self._embedding_mismatch_error)

    def _init_vector_store(self) -> Chroma:
        return Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=self.embeddings,
            collection_name="knowbase",
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
        self._ensure_embedding_compatible()
        return self._retry_after_vector_refresh(
            lambda: self.retriever.hybrid_search(
                query,
                k=k,
                score_threshold=score_threshold,
                vector_candidate_k=vector_candidate_k,
                filter=filter,
                workspace_id=workspace_id,
            ),
            operation_name="hybrid_search",
        )

    def debug_search_breakdown(
        self,
        query: str,
        k: int = TOP_K_RETRIEVAL,
        *,
        filter: dict | None = None,
        vector_candidate_k: int | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, list[RetrievalResult]]:
        self._ensure_embedding_compatible()
        return self._retry_after_vector_refresh(
            lambda: self.retriever.debug_search_breakdown(
                query,
                k=k,
                filter=filter,
                vector_candidate_k=vector_candidate_k,
                workspace_id=workspace_id,
            ),
            operation_name="debug_search_breakdown",
        )

    def get_neighbor_chunks(self, chunk_id: str, window: int = 1, workspace_id: str | None = None) -> list[Document]:
        return self._retry_after_vector_refresh(
            lambda: self.retriever.get_neighbor_chunks(chunk_id, window=window, workspace_id=workspace_id),
            operation_name="get_neighbor_chunks",
        )

    def search_content(self, query: str, workspace_id: str | None = None) -> list[Document]:
        return self._retry_after_vector_refresh(
            lambda: self.retriever.search_content(query, workspace_id=workspace_id),
            operation_name="search_content",
        )

    def load_preset_documents(self, workspace_id: str = "") -> int:
        with self._write_lock:
            self._ensure_embedding_compatible()
            return self.ingestion.load_preset_documents(workspace_id=workspace_id)

    def import_demo_documents(self, workspace_id: str = "") -> tuple[int, list[str]]:
        with self._write_lock:
            self._ensure_embedding_compatible()
            return self.ingestion.import_demo_documents(workspace_id=workspace_id)

    def ingest_file(
        self,
        file_path: str,
        source_name: str | None = None,
        version_mode: str = "replace",
        progress_callback: Callable[[str, int], None] | None = None,
        workspace_id: str = "",
    ) -> int:
        with self._write_lock:
            self._ensure_embedding_compatible()
            return self.ingestion.ingest_file(
                file_path,
                source_name=source_name,
                version_mode=version_mode,
                progress_callback=progress_callback,
                workspace_id=workspace_id,
            )

    def ingest_url(
        self,
        url: str,
        version_mode: str = "replace",
        progress_callback: Callable[[str, int], None] | None = None,
        workspace_id: str = "",
    ) -> int:
        with self._write_lock:
            self._ensure_embedding_compatible()
            return self.ingestion.ingest_url(
                url,
                version_mode=version_mode,
                progress_callback=progress_callback,
                workspace_id=workspace_id,
            )

    def add_document(self, file_path: str, workspace_id: str = "") -> int:
        with self._write_lock:
            self._ensure_embedding_compatible()
            return self.ingestion.add_document(file_path, workspace_id=workspace_id)

    def delete_source(self, source_name: str, workspace_id: str | None = None) -> int:
        with self._write_lock:
            return self.catalog.delete_source(source_name, workspace_id=workspace_id)

    def clear(self) -> None:
        with self._write_lock:
            self.vector_store.delete_collection()
            self.vector_store = self._init_vector_store()
            self.ingestion.vector_store = self.vector_store
            self.retriever.vector_store = self.vector_store
            self.catalog.vector_store = self.vector_store
            self.catalog.clear()
            self._refresh_index_metadata_state()

    def clear_workspace(self, workspace_id: str = "") -> int:
        with self._write_lock:
            return self.catalog.clear_workspace(workspace_id=workspace_id)

    def rebuild_index(self, workspace_id: str = "") -> int:
        with self._write_lock:
            self._ensure_embedding_compatible()
            self.ingestion._ensure_loaded()
            self.ingestion._rebuild_all()
            return self.document_count_for_workspace(workspace_id)

    def get_hotspots(self, top_n: int = 50, workspace_id: str | None = None) -> list[HotspotEntry]:
        return self.catalog.get_hotspots(top_n=top_n, workspace_id=workspace_id)

    def get_chunk_by_id(self, chunk_id: str, workspace_id: str | None = None) -> KBChunk | None:
        return self.catalog.get_chunk_by_id(chunk_id, workspace_id=workspace_id)

    @property
    def document_count(self) -> int:
        return self.retriever.document_count

    def document_count_for_workspace(self, workspace_id: str = "") -> int:
        return self.catalog.document_count_for_workspace(workspace_id)

    def stats(self, workspace_id: str = "") -> dict[str, int]:
        return self.catalog.stats(workspace_id=workspace_id)

    def list_chunks(
        self,
        *,
        workspace_id: str = "",
        source: str = "",
        search: str = "",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[KBChunk]]:
        return self.catalog.list_chunks(
            workspace_id=workspace_id,
            source=source,
            search=search,
            skip=skip,
            limit=limit,
        )

    def source_counts(self, workspace_id: str | None = None) -> list[tuple[str, int]]:
        return self.catalog.source_counts(workspace_id=workspace_id)


__all__ = [
    "CatalogService",
    "EmbeddingIndexMismatchError",
    "HotspotTracker",
    "IngestionService",
    "KnowledgeBase",
    "KnowledgeBaseState",
    "Retriever",
    "RetrievalResult",
    "rrf_fuse",
    "workspace_matches",
]
