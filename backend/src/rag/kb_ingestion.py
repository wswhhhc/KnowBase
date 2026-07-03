"""Document ingestion and index population for the knowledge base."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
import logging
from pathlib import Path
import threading

import jieba
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.settings import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
    ENABLE_CONTEXTUAL_RETRIEVAL,
    get_runtime_setting,
)
from src.rag.kb_state import KnowledgeBaseState, workspace_matches
from src.rag.models import (
    canonical_source_from_metadata,
    content_hash as compute_content_hash,
    infer_source_type,
    metadata_workspace_id,
    normalize_source,
    normalize_workspace_id,
    workspace_chunk_id,
)

logger = logging.getLogger(__name__)


class IngestionService:
    """Handles document loading, splitting, Chroma storage, and BM25 extension."""

    def __init__(
        self,
        vector_store: Chroma,
        state: KnowledgeBaseState,
        document_loader: Callable[[str, str | None], list[Document]],
        url_loader: Callable[[str], list[Document]],
    ):
        self.vector_store = vector_store
        self._state = state
        self._document_loader = document_loader
        self._url_loader = url_loader
        self._all_docs = state.all_docs
        self._doc_by_id = state.doc_by_id
        self._existing_chunk_ids = state.existing_chunk_ids
        self._bm25_corpus = state.bm25_corpus
        self._bm25_index = state.bm25_index_ref
        self._load_lock = threading.Lock()

    @property
    def _loaded(self) -> bool:
        return self._state.docs_loaded

    @_loaded.setter
    def _loaded(self, value: bool) -> None:
        self._state.docs_loaded = value

    def _ensure_loaded(self) -> None:
        """Lazy-load full documents from Chroma only when doc content is required."""
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:
                return
            result = self.vector_store.get(include=["documents", "metadatas"])
            result = self._backfill_legacy_workspace_metadata(result)
            self._state.load_docs(self._documents_from_chroma_result(result))

    def _ensure_bm25_loaded(self) -> None:
        self._ensure_loaded()
        self._state.ensure_bm25(self._tokenize)

    def _backfill_legacy_workspace_metadata(self, result: dict) -> dict:
        """Persist missing workspace metadata for legacy default-workspace rows."""
        ids = list(result.get("ids") or [])
        metadatas = list(result.get("metadatas") or [])
        if not ids or not metadatas:
            return result

        patched_metadatas: list[dict] = []
        update_ids: list[str] = []
        update_metadatas: list[dict] = []

        for index, metadata in enumerate(metadatas):
            patched = dict(metadata or {})
            if "workspace_id" not in patched:
                patched["workspace_id"] = ""
                if index < len(ids):
                    update_ids.append(ids[index])
                    update_metadatas.append(dict(patched))
            patched_metadatas.append(patched)

        if update_ids:
            collection = getattr(self.vector_store, "_collection", None)
            if collection is not None:
                try:
                    collection.update(ids=update_ids, metadatas=update_metadatas)
                except Exception as exc:  # pragma: no cover - defensive fallback
                    logger.warning("旧向量数据 workspace_id 回填失败: %s", exc)

        patched_result = dict(result)
        patched_result["metadatas"] = patched_metadatas
        return patched_result

    def _rebuild_all(self) -> None:
        self._state.rebuild()

    def _extend_bm25(self, new_docs: list[Document]) -> None:
        if new_docs:
            self._state.invalidate_bm25()

    @staticmethod
    def _has_canonical_chunk_id(chunk_id: str) -> bool:
        try:
            prefix, chunk_index, hash_prefix = chunk_id.rsplit(":", 2)
        except ValueError:
            return False
        return bool(prefix) and chunk_index.isdigit() and bool(hash_prefix)

    def _ensure_chunk_ids_ready(self) -> None:
        if self._loaded or not self._existing_chunk_ids:
            return
        if all(self._has_canonical_chunk_id(chunk_id) for chunk_id in self._existing_chunk_ids):
            return
        self._ensure_loaded()

    @staticmethod
    def _documents_from_chroma_result(result: dict) -> list[Document]:
        contents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        ids = result.get("ids") or []

        docs = []
        for index, content in enumerate(contents):
            if not content:
                continue
            metadata = dict(metadatas[index] or {}) if index < len(metadatas) else {}
            source = canonical_source_from_metadata(metadata)
            workspace_id = metadata_workspace_id(metadata)
            content_hash = metadata.get("content_hash") or compute_content_hash(content)
            chunk_index = int(metadata.get("chunk_index", index))
            metadata["source"] = source
            metadata["workspace_id"] = workspace_id
            metadata.setdefault("content_hash", content_hash)
            metadata.setdefault("chunk_index", chunk_index)
            existing_chunk_id = metadata.get("chunk_id")
            expected_prefix = (
                f"{workspace_id}::{source}:{chunk_index}:"
                if workspace_id
                else f"{source}:{chunk_index}:"
            )
            if existing_chunk_id and not str(existing_chunk_id).startswith(expected_prefix):
                metadata["legacy_chunk_id"] = str(existing_chunk_id)
                metadata["chunk_id"] = workspace_chunk_id(
                    workspace_id,
                    source,
                    chunk_index,
                    content_hash,
                )
            elif not existing_chunk_id:
                metadata["chunk_id"] = workspace_chunk_id(
                    workspace_id,
                    source,
                    chunk_index,
                    content_hash,
                )
            metadata.setdefault("legacy_chroma_id", ids[index] if index < len(ids) else "")
            docs.append(Document(page_content=content, metadata=metadata))
        return docs

    @staticmethod
    def _vector_store_id(doc: Document) -> str:
        return str(
            doc.metadata.get("legacy_chroma_id")
            or doc.metadata.get("chunk_id")
            or ""
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]

    @staticmethod
    def _prepare_splits(
        docs: list[Document],
        version_mode: str = "replace",
        version_label: str = "",
        workspace_id: str = "",
    ) -> list[Document]:
        chunk_size = get_runtime_setting("chunk_size", CHUNK_SIZE)
        chunk_overlap = get_runtime_setting("chunk_overlap", CHUNK_OVERLAP)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "！", "？", ""],
        )
        splits = splitter.split_documents(docs)
        per_source_counts: Counter[str] = Counter()
        ingested_at = datetime.now(UTC).isoformat()
        current_heading: dict[str, str] = {}

        for split in splits:
            source = normalize_source(split.metadata.get("source", "unknown"))
            normalized_workspace_id = normalize_workspace_id(workspace_id)
            chunk_index = per_source_counts[source]
            per_source_counts[source] += 1
            content_hash = compute_content_hash(split.page_content)

            first_line = split.page_content.split("\n")[0].strip()
            if first_line.startswith("## ") or first_line.startswith("# "):
                current_heading[source] = first_line.lstrip("#").strip()

            source_type = split.metadata.get("source_type") or infer_source_type(split.metadata.get("source", ""))
            metadata = {
                "source": source,
                "source_type": source_type,
                "workspace_id": normalized_workspace_id,
                "chunk_index": chunk_index,
                "content_hash": content_hash,
                "chunk_id": workspace_chunk_id(
                    normalized_workspace_id,
                    source,
                    chunk_index,
                    content_hash,
                ),
                "section": current_heading.get(source, ""),
                "ingested_at": split.metadata.get("ingested_at", ingested_at),
            }
            if version_mode == "append":
                version = version_label or f"v{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
                metadata["version"] = version
                metadata["version_ingested_at"] = ingested_at
            split.metadata.update(metadata)

        if get_runtime_setting("enable_contextual_retrieval", ENABLE_CONTEXTUAL_RETRIEVAL):
            for split in splits:
                original = split.page_content
                section = split.metadata.get("section", "")
                source = split.metadata.get("source", "")
                context_parts = [f"本段属于文档「{source}」"]
                if section:
                    context_parts.append(f"章节：{section}")
                split.metadata["original_content"] = original
                split.page_content = f"{'，'.join(context_parts)}\n{original}"

        return splits

    def _replace_old_chunks(self, source_name: str, new_docs: list[Document], workspace_id: str = "") -> None:
        self._ensure_loaded()
        source = normalize_source(source_name)
        old_ids = {
            doc.metadata["chunk_id"]
            for doc in self._all_docs
            if normalize_source(doc.metadata.get("source", "")) == source
            and workspace_matches(doc.metadata, workspace_id)
        }
        if not old_ids:
            return
        new_ids = {
            doc.metadata["chunk_id"]
            for doc in self._prepare_splits(new_docs, workspace_id=workspace_id)
            if doc.metadata.get("chunk_id")
        }
        stale_ids = old_ids - new_ids
        if not stale_ids:
            return
        stale_docs = [
            doc
            for doc in self._all_docs
            if doc.metadata.get("chunk_id") in stale_ids
        ]
        vector_ids = [self._vector_store_id(doc) for doc in stale_docs if self._vector_store_id(doc)]
        if vector_ids:
            self.vector_store.delete(ids=vector_ids)
        self._all_docs[:] = [
            doc
            for doc in self._all_docs
            if doc.metadata["chunk_id"] not in stale_ids
        ]
        self._rebuild_all()

    def _source_exists(self, source_name: str, workspace_id: str) -> bool:
        self._ensure_loaded()
        source = normalize_source(source_name)
        return any(
            normalize_source(doc.metadata.get("source", "")) == source
            and workspace_matches(doc.metadata, workspace_id)
            for doc in self._all_docs
        )

    def _next_version_label(self, source_name: str, workspace_id: str) -> str:
        source = normalize_source(source_name)
        existing_versions = {
            str(doc.metadata.get("version", ""))
            for doc in self._all_docs
            if normalize_source(doc.metadata.get("source", "")) == source
            and workspace_matches(doc.metadata, workspace_id)
            and doc.metadata.get("version")
        }
        next_version = 1
        while f"v{next_version}" in existing_versions:
            next_version += 1
        return f"v{next_version}"

    def _ingest_documents(
        self,
        docs: list[Document],
        *,
        source_name: str | None,
        version_mode: str,
        progress_callback: Callable[[str, int], None] | None,
        workspace_id: str,
    ) -> int:
        if source_name and version_mode == "skip" and self._source_exists(source_name, workspace_id):
            return 0

        if progress_callback:
            progress_callback("splitting", 50)

        if source_name and version_mode == "replace":
            self._replace_old_chunks(source_name, docs, workspace_id=workspace_id)

        version_label = ""
        if source_name and version_mode == "append":
            version_label = self._next_version_label(source_name, workspace_id)

        if progress_callback:
            progress_callback("embedding", 75)
        return self._process_documents(
            docs,
            version_mode=version_mode,
            version_label=version_label,
            workspace_id=workspace_id,
        )

    def _process_documents(
        self,
        docs: list[Document],
        version_mode: str = "replace",
        version_label: str = "",
        workspace_id: str = "",
    ) -> int:
        self._ensure_chunk_ids_ready()
        splits = self._prepare_splits(
            docs,
            version_mode=version_mode,
            version_label=version_label,
            workspace_id=workspace_id,
        )
        new_splits = [
            doc
            for doc in splits
            if doc.metadata["chunk_id"] not in self._existing_chunk_ids
        ]
        if not new_splits:
            return 0

        ids = [doc.metadata["chunk_id"] for doc in new_splits]
        self.vector_store.add_documents(new_splits, ids=ids)
        if self._loaded:
            self._all_docs.extend(new_splits)
            for doc in new_splits:
                self._doc_by_id[doc.metadata["chunk_id"]] = doc
        self._existing_chunk_ids.update(doc.metadata["chunk_id"] for doc in new_splits)
        self._extend_bm25(new_splits)
        return len(new_splits)

    def load_preset_documents(self, workspace_id: str = "") -> int:
        total = 0
        for file_path in sorted(Path(DATA_DIR).glob("sample_*.txt")):
            total += self.ingest_file(
                str(file_path),
                source_name=file_path.name,
                workspace_id=workspace_id,
            )
        return total

    def import_demo_documents(self, workspace_id: str = "") -> tuple[int, list[str]]:
        demo_dir = Path(DATA_DIR) / "samples" / "demo"
        if not demo_dir.exists():
            raise ValueError(f"示例资料目录不存在：{demo_dir}")

        demo_files = sorted(file_path for file_path in demo_dir.iterdir() if file_path.is_file())
        if not demo_files:
            raise ValueError("示例资料目录为空，无法导入")

        total = 0
        imported_sources: list[str] = []
        for file_path in demo_files:
            imported_sources.append(file_path.name)
            total += self.ingest_file(
                str(file_path),
                source_name=file_path.name,
                version_mode="replace",
                workspace_id=workspace_id,
            )
        return total, imported_sources

    def ingest_file(
        self,
        file_path: str,
        source_name: str | None = None,
        version_mode: str = "replace",
        progress_callback: Callable[[str, int], None] | None = None,
        workspace_id: str = "",
    ) -> int:
        if progress_callback:
            progress_callback("loading", 25)
        docs = self._document_loader(file_path, source_name)
        return self._ingest_documents(
            docs,
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
        if progress_callback:
            progress_callback("loading", 25)
        docs = self._url_loader(url)
        return self._ingest_documents(
            docs,
            source_name=url,
            version_mode=version_mode,
            progress_callback=progress_callback,
            workspace_id=workspace_id,
        )

    def add_document(self, file_path: str, workspace_id: str = "") -> int:
        return self.ingest_file(file_path, source_name=Path(file_path).name, workspace_id=workspace_id)
