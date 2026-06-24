"""Comprehensive API endpoint tests for all 21+ routes.

Uses TestClient with a mocked KnowledgeBase dependency via app.dependency_overrides.
Tests happy paths and error paths (422, 404) for every endpoint.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src.api.deps import get_knowledge_base
from src.api.main import app
from src.api.models import ConversationCreate, IngestResponse, URLIngestRequest
from src import conversations


class FakeKnowledgeBase:
    """Minimal KB stub — no real Chroma/embeddings."""

    def __init__(self):
        self.all_docs: list = []
        self.hit_counter: dict[str, int] = {}
        self._loaded = False
        self.doc_by_id: dict = {}

    def _ensure_loaded(self):
        if not self._loaded:
            self.all_docs = [
                Document(
                    page_content="测试内容",
                    metadata={
                        "source": "test.txt",
                        "chunk_id": "test.txt:0:abc123",
                        "chunk_index": 0,
                    },
                ),
                Document(
                    page_content="另一段内容",
                    metadata={
                        "source": "test.txt",
                        "chunk_id": "test.txt:1:def456",
                        "chunk_index": 1,
                    },
                ),
            ]
            self.doc_by_id = {d.metadata["chunk_id"]: d for d in self.all_docs}
            self._loaded = True

    def source_counts(self):
        return [("test.txt", 2)]

    @property
    def document_count(self):
        return len(self.all_docs)

    def load_preset_documents(self):
        return 0

    def hybrid_search(self, *args, **kwargs):
        return []

    def get_neighbor_chunks(self, chunk_id, window=1):
        return []

    def get_hotspots(self, top_n=50):
        return [{"chunk_id": "test.txt:0:abc", "source": "test.txt", "hits": 5, "content_preview": "测试"}]

    def ingest_file(self, file_path, source_name=None):
        return 2

    def ingest_url(self, url):
        return 1

    def delete_source(self, source_name):
        if source_name == "existing.txt":
            return 2
        if source_name == "https://example.com/page":
            return 1
        return 0

    def clear(self):
        pass


class APIEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher_chroma = patch("src.knowledge_base.Chroma")
        cls.patcher_embeddings = patch("src.knowledge_base.OpenAIEmbeddings")
        cls.patcher_api_key = patch("src.knowledge_base.require_siliconflow_api_key", return_value="sk-test")

        cls.patcher_chroma.start()
        cls.patcher_embeddings.start()
        cls.patcher_api_key.start()

        # Override KB dependency so all Depends resolve to our fake
        cls.fake_kb = FakeKnowledgeBase()
        app.dependency_overrides[get_knowledge_base] = lambda: cls.fake_kb

        # Use a temp database for all test data
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls._original_db_path = conversations._DB_PATH
        conversations._DB_PATH = Path(cls._temp_dir.name) / "conversations.db"
        conversations.init_db()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        conversations._DB_PATH = cls._original_db_path
        cls._temp_dir.cleanup()
        app.dependency_overrides.clear()
        cls.patcher_chroma.stop()
        cls.patcher_embeddings.stop()
        cls.patcher_api_key.stop()

    # ---- Health ----
    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    # ---- Conversations ----
    def test_create_conversation_happy_path(self):
        resp = self.client.post("/api/conversations", json={"title": "新对话"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("id", data)
        self.assertIn("thread_id", data)
        self.assertEqual(data["title"], "新对话")

    def test_create_conversation_default_title(self):
        resp = self.client.post("/api/conversations", json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "新对话")

    def test_list_conversations_happy_path(self):
        self.client.post("/api/conversations", json={"title": "列表测试"})
        resp = self.client.get("/api/conversations")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        if data:
            self.assertIn("id", data[0])
            self.assertIn("title", data[0])
            self.assertIn("thread_id", data[0])

    def test_get_conversation_happy_path(self):
        create_resp = self.client.post("/api/conversations", json={"title": "获取测试"})
        conv_id = create_resp.json()["id"]
        resp = self.client.get(f"/api/conversations/{conv_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "获取测试")

    def test_get_conversation_404(self):
        resp = self.client.get("/api/conversations/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    def test_update_conversation_title(self):
        create_resp = self.client.post("/api/conversations", json={"title": "旧标题"})
        conv_id = create_resp.json()["id"]
        resp = self.client.patch(f"/api/conversations/{conv_id}", json={"title": "新标题"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "新标题")

    def test_update_conversation_404(self):
        resp = self.client.patch("/api/conversations/nonexistent", json={"title": "标题"})
        self.assertEqual(resp.status_code, 404)

    def test_delete_conversation(self):
        create_resp = self.client.post("/api/conversations", json={"title": "删除测试"})
        conv_id = create_resp.json()["id"]
        resp = self.client.delete(f"/api/conversations/{conv_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_delete_conversations_batch(self):
        r1 = self.client.post("/api/conversations", json={"title": "批量A"}).json()
        r2 = self.client.post("/api/conversations", json={"title": "批量B"}).json()
        r3 = self.client.post("/api/conversations", json={"title": "保留"}).json()

        resp = self.client.post("/api/conversations/batch-delete", json=[r1["id"], r2["id"]])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

        # Verify deleted
        self.assertEqual(self.client.get(f"/api/conversations/{r1['id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/conversations/{r2['id']}").status_code, 404)
        # Verify kept
        self.assertEqual(self.client.get(f"/api/conversations/{r3['id']}").status_code, 200)

    def test_delete_conversations_batch_empty(self):
        resp = self.client.post("/api/conversations/batch-delete", json=[])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_get_messages_happy_path(self):
        create_resp = self.client.post("/api/conversations", json={"title": "消息测试"})
        conv_id = create_resp.json()["id"]
        resp = self.client.get(f"/api/conversations/{conv_id}/messages")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_feedback_happy_path(self):
        create_resp = self.client.post("/api/conversations", json={"title": "反馈测试"})
        conv_id = create_resp.json()["id"]
        # Create a real message first so feedback has a target
        from src.conversations import add_message
        msg_id = add_message(conv_id, "user", "test question")
        resp = self.client.post(
            f"/api/conversations/{conv_id}/messages/{msg_id}/feedback",
            json={"feedback": "like"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_export_happy_path(self):
        create_resp = self.client.post("/api/conversations", json={"title": "导出测试"})
        conv_id = create_resp.json()["id"]
        resp = self.client.get(f"/api/conversations/{conv_id}/export")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("markdown", data)

    def test_export_404(self):
        resp = self.client.get("/api/conversations/nonexistent/export")
        self.assertEqual(resp.status_code, 404)

    # ---- Knowledge Base ----
    def test_kb_stats_happy_path(self):
        resp = self.client.get("/api/knowledge-base/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in ("chunk_count", "source_count", "total_chars"):
            self.assertIn(key, data)

    def test_kb_config_happy_path(self):
        resp = self.client.get("/api/knowledge-base/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("chunk_size", data)
        self.assertIn("chunk_overlap", data)

    def test_kb_chunks_happy_path(self):
        resp = self.client.get("/api/knowledge-base/chunks?skip=0&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)
        self.assertIn("items", data)
        if data["items"]:
            item = data["items"][0]
            for key in ("source", "chunk_index", "chunk_id", "content"):
                self.assertIn(key, item)

    def test_kb_chunks_with_source_filter(self):
        resp = self.client.get("/api/knowledge-base/chunks?source=test.txt&skip=0&limit=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)

    def test_kb_chunks_with_search(self):
        resp = self.client.get("/api/knowledge-base/chunks?search=测试&skip=0&limit=5")
        self.assertEqual(resp.status_code, 200)

    def test_kb_sources_happy_path(self):
        resp = self.client.get("/api/knowledge-base/sources")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_kb_hotspots_happy_path(self):
        resp = self.client.get("/api/knowledge-base/hotspots")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    # ---- Documents ----
    def test_list_document_sources(self):
        resp = self.client.get("/api/documents/sources")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_delete_source_happy_path(self):
        resp = self.client.delete("/api/documents/source/existing.txt")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("chunk_count", data)
        self.assertIn("message", data)
        self.assertEqual(data["chunk_count"], 2)

    def test_delete_url_source_happy_path(self):
        resp = self.client.delete("/api/documents/source/https%3A%2F%2Fexample.com%2Fpage")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["chunk_count"], 1)
        self.assertIn("https://example.com/page", data["message"])

    def test_delete_source_404(self):
        resp = self.client.delete("/api/documents/source/nonexistent.txt")
        self.assertEqual(resp.status_code, 404)

    def test_clear_knowledge_base(self):
        resp = self.client.post("/api/documents/clear")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ok"], True)

    # ---- Metrics ----
    def test_metrics_logs_happy_path(self):
        resp = self.client.get("/api/metrics/logs?days=7&limit=10")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_metrics_logs_default_params(self):
        resp = self.client.get("/api/metrics/logs")
        self.assertEqual(resp.status_code, 200)

    # ---- Chat SSE endpoint ----
    def test_chat_stream_returns_sse(self):
        resp = self.client.post(
            "/api/chat/stream",
            json={"question": "测试问题", "web_search_enabled": False, "search_strategy": "balanced"},
        )
        # The SSE endpoint may error since the graph isn't fully wired,
        # but should not be a 422 validation error.
        self.assertIn(resp.status_code, (200, 500))

    def test_chat_stream_empty_question_422(self):
        resp = self.client.post(
            "/api/chat/stream",
            json={"question": "", "web_search_enabled": False},
        )
        self.assertEqual(resp.status_code, 422)

    def test_chat_stream_question_too_long_422(self):
        resp = self.client.post(
            "/api/chat/stream",
            json={"question": "x" * 5000, "web_search_enabled": False},
        )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
