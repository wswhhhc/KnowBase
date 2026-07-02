"""Shared test helpers — FakeKnowledgeBase, setup/teardown fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

from src.api.deps import get_knowledge_base
from src.api.main import app
from src import conversations


class FakeKnowledgeBase:
    """Minimal KB stub for tests — no real Chroma or embeddings.

    Call ``ensure_all_docs_populated()`` before routes that read
    ``kb.all_docs`` (stats, chunks) to preload sample documents.
    """

    def __init__(self):
        self.all_docs: list = []
        self.hit_counter: dict[str, int] = {}
        self._loaded = False
        self.doc_by_id: dict = {}

    def ensure_all_docs_populated(self):
        if not self.all_docs:
            self.all_docs = [
                Document(
                    page_content="chunk A",
                    metadata={"source": "doc.txt", "chunk_id": "doc.txt:0:aaa", "chunk_index": 0, "workspace_id": ""},
                ),
                Document(
                    page_content="chunk B",
                    metadata={"source": "doc.txt", "chunk_id": "doc.txt:1:bbb", "chunk_index": 1, "workspace_id": ""},
                ),
                Document(
                    page_content="chunk C",
                    metadata={"source": "other.txt", "chunk_id": "other.txt:0:ccc", "chunk_index": 0, "workspace_id": ""},
                ),
            ]
            self.doc_by_id = {d.metadata["chunk_id"]: d for d in self.all_docs}
            self._loaded = True

    def _workspace_docs(self, workspace_id: str | None = None):
        self.ensure_all_docs_populated()
        if workspace_id is None:
            return list(self.all_docs)
        return [doc for doc in self.all_docs if doc.metadata.get("workspace_id", "") == workspace_id]

    def source_counts(self, workspace_id: str | None = None):
        self.ensure_all_docs_populated()
        from collections import Counter
        from src.rag.models import normalize_source
        counts = Counter(
            normalize_source(d.metadata.get("source", "未知来源"))
            for d in self._workspace_docs(workspace_id)
        )
        return sorted(counts.items())

    @property
    def document_count(self):
        return len(self.all_docs)

    def document_count_for_workspace(self, workspace_id: str = ""):
        return len(self._workspace_docs(workspace_id))

    def stats(self, workspace_id: str = ""):
        docs = self._workspace_docs(workspace_id)
        return {
            "chunk_count": len(docs),
            "source_count": len(self.source_counts(workspace_id)),
            "total_chars": sum(len(doc.page_content) for doc in docs),
        }

    def list_chunks(self, *, workspace_id: str = "", source: str = "", search: str = "", skip: int = 0, limit: int = 50):
        docs = self._workspace_docs(workspace_id)
        if source:
            docs = [doc for doc in docs if doc.metadata.get("source") == source]
        if search:
            docs = [doc for doc in docs if search.lower() in doc.page_content.lower()]
        total = len(docs)
        page = docs[skip: skip + limit]
        return total, [
            {
                "source": doc.metadata["source"],
                "chunk_index": doc.metadata["chunk_index"],
                "chunk_id": doc.metadata["chunk_id"],
                "page": doc.metadata.get("page"),
                "content": doc.page_content,
                "original_content": doc.metadata.get("original_content"),
                "section": doc.metadata.get("section"),
            }
            for doc in page
        ]

    def load_preset_documents(self):
        return 0

    def hybrid_search(self, *args, **kwargs):
        return []

    def debug_search_breakdown(self, *args, **kwargs):
        return {"vector_results": [], "bm25_results": [], "fused_results": []}

    def get_neighbor_chunks(self, chunk_id, window=1, workspace_id=None):
        return []

    def get_hotspots(self, top_n=50, workspace_id=None):
        return []

    def get_chunk_by_id(self, chunk_id, workspace_id: str | None = None):
        for doc in self._workspace_docs(workspace_id):
            if doc.metadata["chunk_id"] == chunk_id:
                return {
                    "source": doc.metadata["source"],
                    "chunk_index": doc.metadata["chunk_index"],
                    "chunk_id": chunk_id,
                    "page": doc.metadata.get("page"),
                    "content": doc.page_content,
                    "original_content": doc.metadata.get("original_content"),
                    "section": doc.metadata.get("section"),
                }
        return None

    def ingest_file(self, file_path, source_name=None, version_mode="replace", progress_callback=None, workspace_id=""):
        if progress_callback:
            progress_callback("loading", 25)
        return 0

    def ingest_url(self, url, version_mode="replace", progress_callback=None, workspace_id=""):
        if progress_callback:
            progress_callback("loading", 25)
        return 0

    def delete_source(self, source_name, workspace_id=None):
        return 0

    def clear_workspace(self, workspace_id=""):
        removed = len(self._workspace_docs(workspace_id))
        self.all_docs = [doc for doc in self.all_docs if doc.metadata.get("workspace_id", "") != workspace_id]
        self.doc_by_id = {doc.metadata["chunk_id"]: doc for doc in self.all_docs}
        self._loaded = bool(self.all_docs)
        return removed

    def clear(self):
        self.all_docs.clear()
        self.hit_counter.clear()
        self._loaded = False
        self.doc_by_id.clear()


def setup_test_env():
    """Patch Chroma / Embeddings / API key and return a FakeKnowledgeBase + configured TestClient.

    Usage::

        fake_kb, client, tmp_dir = setup_test_env()
        app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
        # ... run tests ...
        teardown_test_env(tmp_dir)
    """
    patcher_chroma = patch("src.rag.knowledge_base.Chroma")
    patcher_emb = patch("src.rag.knowledge_base.OpenAIEmbeddings")
    patcher_api = patch("src.rag.knowledge_base.require_siliconflow_api_key", return_value="sk-test")

    patcher_chroma.start()
    patcher_emb.start()
    patcher_api.start()

    fake_kb = FakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb

    tmp_dir = tempfile.TemporaryDirectory()
    orig_db = conversations._DB_PATH
    conversations._DB_PATH = Path(tmp_dir.name) / "conv.db"
    conversations.init_db()

    from fastapi.testclient import TestClient
    client = TestClient(app)

    return fake_kb, client, tmp_dir, orig_db, (patcher_chroma, patcher_emb, patcher_api)


def teardown_test_env(tmp_dir, orig_db, patchers):
    """Undo setup_test_env changes."""
    conversations._DB_PATH = orig_db
    tmp_dir.cleanup()
    app.dependency_overrides.clear()
    for p in patchers:
        p.stop()
