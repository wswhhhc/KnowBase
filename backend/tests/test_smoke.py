"""Smoke tests for the FastAPI application.

These tests verify that the API starts, routes are mounted, and basic
responses return the expected shapes. Heavy mocking is avoided —
only the knowledge base dependency is overridden to avoid real Chroma/LLM calls.
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src.api.deps import get_knowledge_base
from src.api.main import app


class FakeKnowledgeBase:
    """Minimal KB stub for smoke tests — no real Chroma or embeddings."""

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
            ]
            self.doc_by_id = {d.metadata["chunk_id"]: d for d in self.all_docs}
            self._loaded = True

    def source_counts(self):
        return [("test.txt", 1)]

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
        return 0

    def ingest_url(self, url):
        return 0

    def delete_source(self, source_name):
        return 0

    def clear(self):
        pass


class FastAPISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher_chroma = patch("src.knowledge_base.Chroma")
        cls.patcher_embeddings = patch("src.knowledge_base.OpenAIEmbeddings")
        cls.patcher_api_key = patch("src.knowledge_base.require_siliconflow_api_key", return_value="sk-test")

        cls.patcher_chroma.start()
        cls.patcher_embeddings.start()
        cls.patcher_api_key.start()

        # Override the KB dependency so Depends resolves to our fake
        cls.fake_kb = FakeKnowledgeBase()
        app.dependency_overrides[get_knowledge_base] = lambda: cls.fake_kb

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.patcher_chroma.stop()
        cls.patcher_embeddings.stop()
        cls.patcher_api_key.stop()

    def test_health_endpoint_returns_ok(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_create_conversation_returns_created(self):
        resp = self.client.post("/api/conversations", json={"title": "测试对话"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("id", data)
        self.assertIn("thread_id", data)
        self.assertEqual(data["title"], "测试对话")

    def test_list_conversations_returns_list(self):
        resp = self.client.get("/api/conversations")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_get_conversation_messages_returns_array(self):
        create_resp = self.client.post("/api/conversations", json={"title": "消息测试"})
        conv_id = create_resp.json()["id"]

        resp = self.client.get(f"/api/conversations/{conv_id}/messages")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_knowledge_base_stats_returns_stats(self):
        resp = self.client.get("/api/knowledge-base/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("chunk_count", data)
        self.assertIn("source_count", data)
        self.assertIn("total_chars", data)

    def test_knowledge_base_config_returns_config(self):
        resp = self.client.get("/api/knowledge-base/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("chunk_size", data)
        self.assertIn("chunk_overlap", data)

    def test_knowledge_base_chunks_returns_paginated_items(self):
        resp = self.client.get("/api/knowledge-base/chunks?skip=0&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertIsInstance(data["items"], list)

    def test_knowledge_base_sources_returns_sorted_list(self):
        resp = self.client.get("/api/knowledge-base/sources")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_unknown_conversation_returns_404(self):
        resp = self.client.get("/api/conversations/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    def test_delete_unknown_conversation_returns_ok(self):
        resp = self.client.delete("/api/conversations/nonexistent-id")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
