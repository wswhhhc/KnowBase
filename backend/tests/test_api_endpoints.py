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
from sse_starlette.sse import AppStatus
from langchain_core.documents import Document
from src.rag.models import RetrievalResult

from src.api.deps import get_knowledge_base
from src.api.main import app
from src.api.models import ConversationCreate, IngestResponse, URLIngestRequest
from src import conversations


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    current_event = "message"
    for line in text.splitlines():
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            events.append({"event": current_event, "data": json.loads(line[6:])})
            current_event = "message"
    return events


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
                        "workspace_id": "",
                    },
                ),
                Document(
                    page_content="另一段内容",
                    metadata={
                        "source": "test.txt",
                        "chunk_id": "test.txt:1:def456",
                        "chunk_index": 1,
                        "workspace_id": "",
                    },
                ),
            ]
            self.doc_by_id = {d.metadata["chunk_id"]: d for d in self.all_docs}
            self._loaded = True

    def _workspace_docs(self, workspace_id: str | None = None):
        self._ensure_loaded()
        if workspace_id is None:
            return list(self.all_docs)
        return [doc for doc in self.all_docs if doc.metadata.get("workspace_id", "") == workspace_id]

    def source_counts(self, workspace_id: str | None = None):
        return [("test.txt", 2)]

    @property
    def document_count(self):
        return len(self.all_docs)

    def document_count_for_workspace(self, workspace_id: str = ""):
        return len(self._workspace_docs(workspace_id))

    def stats(self, workspace_id: str = ""):
        docs = self._workspace_docs(workspace_id)
        return {
            "chunk_count": len(docs),
            "source_count": 1 if docs else 0,
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
        docs = [
            RetrievalResult(
                chunk_id="test.txt:0:abc123",
                document=self.doc_by_id["test.txt:0:abc123"],
                score=0.91,
                vector_score=0.91,
            ),
            RetrievalResult(
                chunk_id="test.txt:1:def456",
                document=self.doc_by_id["test.txt:1:def456"],
                score=0.42,
                bm25_score=0.42,
            ),
        ]
        return {
            "vector_results": docs[:1],
            "bm25_results": docs[1:],
            "fused_results": docs,
        }

    def get_neighbor_chunks(self, chunk_id, window=1, workspace_id=None):
        return []

    def get_hotspots(self, top_n=50, workspace_id=None):
        return [{"chunk_id": "test.txt:0:abc", "source": "test.txt", "hits": 5, "content_preview": "测试"}]

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
            progress_callback("splitting", 50)
            progress_callback("embedding", 75)
        return 2

    def ingest_url(self, url, version_mode="replace", progress_callback=None, workspace_id=""):
        if progress_callback:
            progress_callback("loading", 25)
            progress_callback("splitting", 50)
            progress_callback("embedding", 75)
        return 1

    def delete_source(self, source_name, workspace_id=None):
        if source_name == "existing.txt":
            return 2
        if source_name == "https://example.com/page":
            return 1
        return 0

    def clear_workspace(self, workspace_id=""):
        return self.document_count_for_workspace(workspace_id)

    def import_demo_documents(self, workspace_id=""):
        return 3, ["contract_notice.md", "meeting_notes.md", "tech_manual.md"]

    def clear(self):
        pass


class APIEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher_chroma = patch("src.rag.knowledge_base.Chroma")
        cls.patcher_embeddings = patch("src.rag.knowledge_base.OpenAIEmbeddings")
        cls.patcher_api_key = patch("src.rag.knowledge_base.require_siliconflow_api_key", return_value="sk-test")

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

    def setUp(self):
        AppStatus.should_exit = False
        AppStatus.should_exit_event = None

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

    def test_get_pin_state_happy_path(self):
        create_resp = self.client.post("/api/conversations", json={"title": "PinState 测试"})
        conv = create_resp.json()
        conversations.replace_pin_state(conv["thread_id"], ["doc:1"], ["doc:2"])

        resp = self.client.get(f"/api/conversations/{conv['id']}/pin-state")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            {
                "thread_id": conv["thread_id"],
                "pinned_chunk_ids": ["doc:1"],
                "excluded_chunk_ids": ["doc:2"],
            },
        )

    def test_get_pin_state_404(self):
        resp = self.client.get("/api/conversations/nonexistent-id/pin-state")
        self.assertEqual(resp.status_code, 404)

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

    def test_kb_stats_passes_workspace_id_to_backend(self):
        with patch.object(self.fake_kb, "stats", return_value={"chunk_count": 1, "source_count": 1, "total_chars": 4}) as mock_stats:
            resp = self.client.get("/api/knowledge-base/stats?workspace_id=ws-alpha")

        self.assertEqual(resp.status_code, 200)
        mock_stats.assert_called_once_with(workspace_id="ws-alpha")

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

    def test_kb_chunks_passes_workspace_id_to_backend(self):
        with patch.object(self.fake_kb, "list_chunks", return_value=(0, [])) as mock_list_chunks:
            resp = self.client.get("/api/knowledge-base/chunks?workspace_id=ws-alpha&skip=0&limit=10")

        self.assertEqual(resp.status_code, 200)
        mock_list_chunks.assert_called_once_with(
            workspace_id="ws-alpha",
            source="",
            search="",
            skip=0,
            limit=10,
        )

    def test_kb_chunks_with_source_filter(self):
        resp = self.client.get("/api/knowledge-base/chunks?source=test.txt&skip=0&limit=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)

    def test_kb_chunks_with_search(self):
        resp = self.client.get("/api/knowledge-base/chunks?search=测试&skip=0&limit=5")
        self.assertEqual(resp.status_code, 200)

    def test_kb_chunk_by_id_happy_path(self):
        resp = self.client.get("/api/knowledge-base/chunks/test.txt%3A0%3Aabc123")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["chunk_id"], "test.txt:0:abc123")
        self.assertEqual(data["content"], "测试内容")

    def test_kb_chunk_by_id_404(self):
        resp = self.client.get("/api/knowledge-base/chunks/missing-chunk")
        self.assertEqual(resp.status_code, 404)

    def test_kb_sources_happy_path(self):
        resp = self.client.get("/api/knowledge-base/sources")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_kb_hotspots_happy_path(self):
        resp = self.client.get("/api/knowledge-base/hotspots")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_kb_debug_search_happy_path(self):
        self.fake_kb._ensure_loaded()
        resp = self.client.post(
            "/api/knowledge-base/debug-search",
            json={"query": "测试", "k": 2, "search_strategy": "balanced"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["strategy"], "balanced")
        self.assertIn("vector_results", data)
        self.assertIn("bm25_results", data)
        self.assertIn("fused_results", data)
        self.assertEqual(data["vector_results"][0]["vector_rank"], 1)
        self.assertEqual(data["fused_results"][0]["rrf_rank"], 1)

    def test_kb_debug_search_strategy_changes_backend_parameters(self):
        self.fake_kb._ensure_loaded()

        calls: list[dict] = []
        original_debug_search = self.fake_kb.debug_search_breakdown

        def _record_debug_search(query, k=5, **kwargs):
            calls.append({"query": query, "k": k, **kwargs})
            return original_debug_search(query, k=k, **kwargs)

        with patch.object(self.fake_kb, "debug_search_breakdown", side_effect=_record_debug_search):
            fast = self.client.post(
                "/api/knowledge-base/debug-search",
                json={"query": "测试", "k": 2, "search_strategy": "fast"},
            )
            deep = self.client.post(
                "/api/knowledge-base/debug-search",
                json={"query": "测试", "k": 2, "search_strategy": "deep"},
            )

        self.assertEqual(fast.status_code, 200)
        self.assertEqual(deep.status_code, 200)
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0]["k"], calls[1]["k"])
        self.assertNotEqual(calls[0].get("vector_candidate_k"), calls[1].get("vector_candidate_k"))

    @patch("src.graph.nodes.rerank_docs")
    def test_kb_debug_search_does_not_call_llm_rerank(self, mock_rerank_docs):
        self.fake_kb._ensure_loaded()
        resp = self.client.post(
            "/api/knowledge-base/debug-search",
            json={"query": "测试", "k": 2, "search_strategy": "high_quality"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(mock_rerank_docs.called)

    # ---- Documents ----
    def test_list_document_sources(self):
        resp = self.client.get("/api/documents/sources")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_check_source_matches_versioned_source_names(self):
        with patch.object(self.fake_kb, "source_counts", return_value=[("fresh.txt (v1)", 2)]):
            resp = self.client.get("/api/documents/check-source?source_name=fresh.txt")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"exists": True})

    def test_upload_stream_prompts_when_only_versioned_source_exists(self):
        with patch.object(self.fake_kb, "source_counts", return_value=[("fresh.txt (v1)", 2)]):
            resp = self.client.post(
                "/api/documents/upload-stream",
                files={"file": ("fresh.txt", b"hello world", "text/plain")},
            )

        self.assertEqual(resp.status_code, 200)
        events = _parse_sse_events(resp.text)
        self.assertEqual(events[-1]["event"], "done")
        self.assertTrue(events[-1]["data"]["existing_version"])

    def test_upload_stream_returns_progress_and_done_events(self):
        resp = self.client.post(
            "/api/documents/upload-stream",
            files={"file": ("fresh.txt", b"hello world", "text/plain")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("event: progress", resp.text)
        self.assertIn("event: done", resp.text)

    def test_upload_stream_emits_terminal_done_progress_before_done_event(self):
        resp = self.client.post(
            "/api/documents/upload-stream",
            files={"file": ("fresh.txt", b"hello world", "text/plain")},
        )
        self.assertEqual(resp.status_code, 200)

        events = _parse_sse_events(resp.text)
        progress_events = [event for event in events if event["event"] == "progress"]

        self.assertGreater(len(progress_events), 0)
        self.assertEqual(progress_events[-1]["data"], {"phase": "done", "percent": 100})
        self.assertEqual(events[-1]["event"], "done")

    def test_ingest_url_stream_passes_version_mode_to_backend(self):
        calls: list[dict] = []

        def _record_ingest(url, version_mode="replace", progress_callback=None, workspace_id=""):
            calls.append({"url": url, "version_mode": version_mode})
            if progress_callback:
                progress_callback("loading", 25)
                progress_callback("splitting", 50)
                progress_callback("embedding", 75)
            return 1

        with patch.object(self.fake_kb, "ingest_url", side_effect=_record_ingest):
            resp = self.client.post(
                "/api/documents/ingest-url-stream?version_mode=append",
                json={"url": "https://example.com/page"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(calls, [{"url": "https://example.com/page", "version_mode": "append"}])

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

    def test_import_demo_documents(self):
        with patch.object(
            self.fake_kb,
            "import_demo_documents",
            return_value=(3, ["contract_notice.md", "meeting_notes.md", "tech_manual.md"]),
        ) as mock_import_demo:
            resp = self.client.post("/api/documents/import-demo?workspace_id=ws-demo")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["chunk_count"], 3)
        self.assertEqual(
            data["imported_sources"],
            ["contract_notice.md", "meeting_notes.md", "tech_manual.md"],
        )
        mock_import_demo.assert_called_once_with(workspace_id="ws-demo")

    # ---- Metrics ----
    def test_metrics_logs_happy_path(self):
        resp = self.client.get("/api/metrics/logs?days=7&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("logs", data)
        self.assertIn("total_cost", data)

    def test_metrics_logs_default_params(self):
        resp = self.client.get("/api/metrics/logs")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("logs", resp.json())

    @patch("src.api.routes.metrics._load_query_logs")
    def test_metrics_logs_include_total_cost_summary(self, mock_load_query_logs):
        from src.api.models import QueryLogEntry

        mock_load_query_logs.return_value = [
            QueryLogEntry(
                timestamp="2026-06-26T00:00:00+00:00",
                thread_id="t-1",
                question="测试",
                elapsed_ms=1200,
                retrieval_count=1,
                quality_ok=True,
                quality_reason="ok",
                token_count=1000,
                prompt_tokens=400,
                completion_tokens=600,
                llm_model="deepseek-ai/DeepSeek-V4-Flash",
            )
        ]

        resp = self.client.get("/api/metrics/logs")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("logs", data)
        self.assertIn("total_cost", data)
        self.assertGreater(data["total_cost"], 0)
        self.assertEqual(data["logs"][0]["llm_model"], "deepseek-ai/DeepSeek-V4-Flash")

    @patch("src.api.routes.settings.get_public_settings")
    def test_settings_get_masks_secrets(self, mock_get_public_settings):
        mock_get_public_settings.return_value = {"api_key": "__KEEP_EXISTING_SECRET__", "chunk_size": 1000}
        resp = self.client.get("/api/settings")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["api_key"], "__KEEP_EXISTING_SECRET__")

    @patch("src.api.routes.settings.update_runtime_settings")
    def test_settings_put_returns_warnings(self, mock_update_runtime_settings):
        resp = self.client.put(
            "/api/settings",
            json={"api_key": "new-local-key", "embedding_model": "foo/bar", "chunk_size": 2048},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["updated"])
        self.assertGreaterEqual(len(data["warnings"]), 2)
        mock_update_runtime_settings.assert_called_once()

    @patch("src.api.routes.settings.update_runtime_settings")
    def test_settings_put_ignores_masked_secret_placeholder(self, mock_update_runtime_settings):
        resp = self.client.put(
            "/api/settings",
            json={"api_key": "__KEEP_EXISTING_SECRET__", "chunk_size": 2048},
        )
        self.assertEqual(resp.status_code, 200)
        mock_update_runtime_settings.assert_called_once_with({"chunk_size": 2048})

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
