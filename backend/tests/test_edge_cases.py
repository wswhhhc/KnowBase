"""Edge case tests for the KnowBase API and conversations module.

Covers empty / ultra-long questions, non-existent resource 404s,
pagination edge cases, and conversation CRUD edge cases.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src.api.deps import get_knowledge_base
from src.api.main import app
from src import conversations
from src.persistence import database


class FakeKnowledgeBase:
    """KB with 3 documents for pagination and edge case testing."""

    def __init__(self):
        self.all_docs: list = []
        self.hit_counter: dict[str, int] = {}
        self._loaded = False
        self.doc_by_id: dict = {}

    def _ensure_loaded(self):
        pass  # no-op; all_docs is populated in __init__ below

    def ensure_all_docs_populated(self):
        """Backwards compat — populate docs on first stats/chunks call."""
        if not self.all_docs:
            self.all_docs = [
                Document(
                    page_content="chunk A",
                    metadata={
                        "source": "doc.txt",
                        "chunk_id": "doc.txt:0:aaa",
                        "chunk_index": 0,
                        "workspace_id": "",
                    },
                ),
                Document(
                    page_content="chunk B",
                    metadata={
                        "source": "doc.txt",
                        "chunk_id": "doc.txt:1:bbb",
                        "chunk_index": 1,
                        "workspace_id": "",
                    },
                ),
                Document(
                    page_content="chunk C",
                    metadata={
                        "source": "other.txt",
                        "chunk_id": "other.txt:0:ccc",
                        "chunk_index": 0,
                        "workspace_id": "",
                    },
                ),
            ]
            self.doc_by_id = {d.metadata["chunk_id"]: d for d in self.all_docs}

    def _workspace_docs(self, workspace_id: str | None = None):
        self.ensure_all_docs_populated()
        if workspace_id is None:
            return list(self.all_docs)
        return [doc for doc in self.all_docs if doc.metadata.get("workspace_id", "") == workspace_id]

    def source_counts(self, workspace_id: str | None = None):
        self.ensure_all_docs_populated()
        docs = self._workspace_docs(workspace_id)
        if not docs:
            return []
        counts = {}
        for doc in docs:
            counts[doc.metadata["source"]] = counts.get(doc.metadata["source"], 0) + 1
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

    def get_neighbor_chunks(self, chunk_id, window=1, workspace_id=None):
        return []

    def get_hotspots(self, top_n=50, workspace_id=None):
        return []

    def ingest_file(self, file_path, source_name=None, workspace_id=""):
        return 0

    def ingest_url(self, url, workspace_id=""):
        return 0

    def delete_source(self, source_name, workspace_id=None):
        return 0

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

    def clear_workspace(self, workspace_id=""):
        return 0

    def clear(self):
        pass


class EmptyKB(FakeKnowledgeBase):
    """KB with no documents at all."""

    def ensure_all_docs_populated(self):
        self.all_docs = []
        self.doc_by_id = {}
        self._loaded = True

    def _ensure_loaded(self):
        if not self._loaded:
            self.all_docs = []
            self.doc_by_id = {}
            self._loaded = True

    def source_counts(self, workspace_id: str | None = None):
        return []

    @property
    def document_count(self):
        return 0


class APIEdgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher_chroma = patch("src.rag.knowledge_base.Chroma")
        cls.patcher_embeddings = patch("src.rag.knowledge_base.OpenAIEmbeddings")
        cls.patcher_api_key = patch("src.rag.knowledge_base.require_siliconflow_api_key", return_value="sk-test")

        cls.patcher_chroma.start()
        cls.patcher_embeddings.start()
        cls.patcher_api_key.start()

        # Use a temp database for all test data
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls._original_db_path = conversations._DB_PATH
        conversations._DB_PATH = Path(cls._temp_dir.name) / "conversations.db"
        conversations.init_db()

    @classmethod
    def tearDownClass(cls):
        conversations._DB_PATH = cls._original_db_path
        database.clear_db_path_override()
        cls._temp_dir.cleanup()
        cls.patcher_chroma.stop()
        cls.patcher_embeddings.stop()
        cls.patcher_api_key.stop()

    @classmethod
    def tearDownClass(cls):
        cls.patcher_chroma.stop()
        cls.patcher_embeddings.stop()
        cls.patcher_api_key.stop()

    def test_non_existent_conversation_returns_404(self):
        with patch("src.api.deps.get_knowledge_base", return_value=FakeKnowledgeBase()):
            client = TestClient(app)
            resp = client.get("/api/conversations/nonexistent-id")
            self.assertEqual(resp.status_code, 404)

    def test_empty_kb_stats(self):
        fake = EmptyKB()
        app.dependency_overrides[get_knowledge_base] = lambda: fake
        client = TestClient(app)
        try:
            resp = client.get("/api/knowledge-base/stats")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["chunk_count"], 0)
            self.assertEqual(data["total_chars"], 0)
        finally:
            app.dependency_overrides.clear()

    def test_pagination_skip_zero(self):
        fake = FakeKnowledgeBase()
        fake.ensure_all_docs_populated()
        app.dependency_overrides[get_knowledge_base] = lambda: fake
        client = TestClient(app)
        try:
            resp = client.get("/api/knowledge-base/chunks?skip=0&limit=2")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(len(data["items"]), 2)
            self.assertEqual(data["total"], 3)
        finally:
            app.dependency_overrides.clear()

    def test_pagination_skip_beyond_total(self):
        fake = FakeKnowledgeBase()
        fake.ensure_all_docs_populated()
        app.dependency_overrides[get_knowledge_base] = lambda: fake
        client = TestClient(app)
        try:
            resp = client.get("/api/knowledge-base/chunks?skip=100&limit=10")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(len(data["items"]), 0)
            self.assertEqual(data["total"], 3)
        finally:
            app.dependency_overrides.clear()

    def test_pagination_partial_last_page(self):
        fake = FakeKnowledgeBase()
        fake.ensure_all_docs_populated()
        app.dependency_overrides[get_knowledge_base] = lambda: fake
        client = TestClient(app)
        try:
            resp = client.get("/api/knowledge-base/chunks?skip=2&limit=2")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(len(data["items"]), 1)
            self.assertEqual(data["total"], 3)
        finally:
            app.dependency_overrides.clear()

    def test_nonexistent_source_name_in_chunks(self):
        fake = FakeKnowledgeBase()
        app.dependency_overrides[get_knowledge_base] = lambda: fake
        client = TestClient(app)
        try:
            resp = client.get("/api/knowledge-base/chunks?source=nonexistent.txt")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(len(data["items"]), 0)
        finally:
            app.dependency_overrides.clear()

    def test_empty_messages_list(self):
        with patch("src.api.deps.get_knowledge_base", return_value=FakeKnowledgeBase()):
            client = TestClient(app)
            create_resp = client.post("/api/conversations", json={"title": "空消息测试"})
            conv_id = create_resp.json()["id"]
            resp = client.get(f"/api/conversations/{conv_id}/messages")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), [])

    def test_export_empty_conversation_returns_basic_markdown(self):
        with patch("src.api.deps.get_knowledge_base", return_value=FakeKnowledgeBase()):
            client = TestClient(app)
            create_resp = client.post("/api/conversations", json={"title": "空导出"})
            conv_id = create_resp.json()["id"]
            resp = client.get(f"/api/conversations/{conv_id}/export")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("空导出", data["markdown"])

    def test_nonexistent_export_returns_404(self):
        with patch("src.api.deps.get_knowledge_base", return_value=FakeKnowledgeBase()):
            client = TestClient(app)
            resp = client.get("/api/conversations/nonexistent/export")
            self.assertEqual(resp.status_code, 404)


class ConversationEdgeCaseAPITests(unittest.TestCase):
    """Additional edge cases covered via the conversations module directly."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "conversations.db"
        self.original_path = conversations._DB_PATH
        conversations._DB_PATH = self.db_path
        conversations.init_db()

    def tearDown(self):
        conversations._DB_PATH = self.original_path
        database.clear_db_path_override()
        self.temp_dir.cleanup()

    def test_create_conversation_without_thread_id_uses_conv_id(self):
        conv = conversations.create_conversation("测试")
        # When no thread_id is provided, it defaults to conv_id
        self.assertEqual(conv["thread_id"], conv["id"])

    def test_create_conversation_with_custom_thread_id(self):
        conv = conversations.create_conversation("测试", thread_id="custom-thread")
        self.assertEqual(conv["thread_id"], "custom-thread")

    def test_get_conversation_by_thread_returns_correct_one(self):
        conv1 = conversations.create_conversation("A", thread_id="thread-a")
        conv2 = conversations.create_conversation("B", thread_id="thread-b")
        result = conversations.get_conversation_by_thread("thread-a")
        self.assertEqual(result["id"], conv1["id"])
        self.assertEqual(result["title"], "A")

    def test_add_message_without_sources(self):
        conv = conversations.create_conversation("无来源")
        conversations.add_message(conv["id"], "user", "你好")
        msgs = conversations.get_messages(conv["id"])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["sources"], [])

    def test_list_conversations_ordered_by_update(self):
        conv_a = conversations.create_conversation("A")
        conv_b = conversations.create_conversation("B")
        listings = conversations.list_conversations()
        self.assertEqual(listings[0]["id"], conv_b["id"])  # Most recent first

    def test_get_messages_from_nonexistent_conversation(self):
        msgs = conversations.get_messages("nonexistent")
        self.assertEqual(msgs, [])

    def test_update_title_on_nonexistent_conversation_does_not_raise(self):
        try:
            conversations.update_title("nonexistent", "新标题")
        except Exception as e:
            self.fail(f"update_title on non-existent conv raised {e}")


if __name__ == "__main__":
    unittest.main()
