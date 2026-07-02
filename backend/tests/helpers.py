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
                    metadata={"source": "doc.txt", "chunk_id": "doc.txt:0:aaa", "chunk_index": 0},
                ),
                Document(
                    page_content="chunk B",
                    metadata={"source": "doc.txt", "chunk_id": "doc.txt:1:bbb", "chunk_index": 1},
                ),
                Document(
                    page_content="chunk C",
                    metadata={"source": "other.txt", "chunk_id": "other.txt:0:ccc", "chunk_index": 0},
                ),
            ]
            self.doc_by_id = {d.metadata["chunk_id"]: d for d in self.all_docs}
            self._loaded = True

    def source_counts(self):
        self.ensure_all_docs_populated()
        from collections import Counter
        from src.rag.models import normalize_source
        counts = Counter(
            normalize_source(d.metadata.get("source", "未知来源"))
            for d in self.all_docs
        )
        return sorted(counts.items())

    @property
    def document_count(self):
        return len(self.all_docs)

    def load_preset_documents(self):
        return 0

    def hybrid_search(self, *args, **kwargs):
        return []

    def debug_search_breakdown(self, *args, **kwargs):
        return {"vector_results": [], "bm25_results": [], "fused_results": []}

    def get_neighbor_chunks(self, chunk_id, window=1):
        return []

    def get_hotspots(self, top_n=50):
        return []

    def ingest_file(self, file_path, source_name=None, version_mode="replace", progress_callback=None):
        if progress_callback:
            progress_callback("loading", 25)
        return 0

    def ingest_url(self, url, version_mode="replace", progress_callback=None):
        if progress_callback:
            progress_callback("loading", 25)
        return 0

    def delete_source(self, source_name):
        return 0

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
