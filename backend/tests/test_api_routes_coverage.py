"""Extended API route coverage — error paths for documents, KB, metrics, conversations."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.documents import Document
from src.rag.models import RetrievalResult

from src.api.deps import get_knowledge_base
from src.api.main import app
from src.api.rate_limit import enforce_document_import_rate_limit
from tests.helpers import init_temp_database, teardown_temp_database


class FakeKnowledgeBase:
    """Minimal KB stub (reused from test_api_endpoints)."""

    def __init__(self):
        self._loaded = False
        self.all_docs = []
        self.doc_by_id = {}

    def _ensure_loaded(self):
        if not self._loaded:
            from langchain_core.documents import Document
            self.all_docs = [
                Document(page_content="test", metadata={"source": "test.txt", "chunk_id": "test.txt:0:abc", "chunk_index": 0, "workspace_id": ""}),
            ]
            self.doc_by_id = {doc.metadata["chunk_id"]: doc for doc in self.all_docs}
            self._loaded = True

    def _workspace_docs(self, workspace_id: str | None = None):
        self._ensure_loaded()
        if workspace_id is None:
            return list(self.all_docs)
        return [doc for doc in self.all_docs if doc.metadata.get("workspace_id", "") == workspace_id]

    def source_counts(self, workspace_id: str | None = None):
        return [("test.txt", 1)]

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
        self._ensure_loaded()
        doc = self.all_docs[0]
        result = RetrievalResult(
            chunk_id="test.txt:0:abc",
            document=doc,
            score=0.88,
            vector_score=0.88,
        )
        return {"vector_results": [result], "bm25_results": [result], "fused_results": [result]}

    def get_neighbor_chunks(self, chunk_id, window=1, workspace_id=None):
        return []

    def get_hotspots(self, top_n=50, workspace_id=None):
        return [{"chunk_id": "test.txt:0:abc", "source": "test.txt", "hits": 5, "content_preview": "test"}]

    def get_chunk_by_id(self, chunk_id, workspace_id: str | None = None):
        self._ensure_loaded()
        doc = next((doc for doc in self._workspace_docs(workspace_id) if doc.metadata["chunk_id"] == chunk_id), None)
        if doc is None:
            return None
        return {
            "source": doc.metadata["source"],
            "chunk_index": doc.metadata["chunk_index"],
            "chunk_id": chunk_id,
            "page": doc.metadata.get("page"),
            "content": doc.page_content,
            "original_content": doc.metadata.get("original_content"),
            "section": doc.metadata.get("section"),
        }

    def ingest_file(self, file_path, source_name=None, version_mode="replace", progress_callback=None, workspace_id=""):
        if progress_callback:
            progress_callback("loading", 25)
        return 2

    def ingest_url(self, url, version_mode="replace", progress_callback=None, workspace_id=""):
        if progress_callback:
            progress_callback("loading", 25)
        return 1

    def delete_source(self, source_name, workspace_id=None):
        if source_name == "existing.txt":
            return 2
        if source_name == "https://example.com/page":
            return 1
        return 0

    def clear_workspace(self, workspace_id=""):
        return self.document_count_for_workspace(workspace_id)

    def clear(self):
        self.all_docs = []
        self.doc_by_id = {}
        self._loaded = False


class APIRoutesCoverageTests(unittest.TestCase):
    """Error-path coverage for documents, knowledge_base, metrics routes."""

    @classmethod
    def setUpClass(cls):
        cls.fake_kb = FakeKnowledgeBase()
        app.dependency_overrides[get_knowledge_base] = lambda: cls.fake_kb

        # Disable rate limiting for these error-path coverage tests
        app.dependency_overrides[enforce_document_import_rate_limit] = lambda: None

        # Use a temp database for all test data
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls._original_db_path = Path(cls._temp_dir.name) / "conversations.db"
        init_temp_database(cls._original_db_path)

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        teardown_temp_database()
        cls._temp_dir.cleanup()
        app.dependency_overrides.clear()

    # ── Documents routes ──

    def test_upload_invalid_file_returns_error(self):
        """Upload with empty/invalid file content should produce 400 or 422."""
        response = self.client.post("/api/documents/upload", files={"file": ("test.exe", b"fake", "application/octet-stream")})
        self.assertIn(response.status_code, (400, 422))

    def test_upload_no_file_returns_422(self):
        response = self.client.post("/api/documents/upload")
        self.assertEqual(response.status_code, 422)

    def test_ingest_url_empty_returns_422(self):
        response = self.client.post("/api/documents/ingest-url", json={"url": ""})
        self.assertEqual(response.status_code, 422)

    def test_ingest_url_invalid_format_returns_422(self):
        response = self.client.post("/api/documents/ingest-url", json={"url": "not-a-url"})
        self.assertEqual(response.status_code, 422)

    def test_delete_source_nonexistent_returns_404(self):
        """DB returns 0 removed rows → 404."""
        response = self.client.delete("/api/documents/source/nonexistent.txt")
        self.assertEqual(response.status_code, 404)

    def test_delete_source_existing(self):
        response = self.client.delete("/api/documents/source/existing.txt")
        self.assertEqual(response.status_code, 200)

    def test_delete_url_source_existing(self):
        response = self.client.delete("/api/documents/source/https%3A%2F%2Fexample.com%2Fpage")
        self.assertEqual(response.status_code, 200)

    def test_clear_knowledge_base(self):
        response = self.client.post("/api/documents/clear")
        self.assertEqual(response.status_code, 200)

    # ── Knowledge Base routes ──

    def test_chunks_source_filter_no_results(self):
        """Filter by a source that doesn't exist → empty items."""
        response = self.client.get("/api/knowledge-base/chunks?source=nonexistent.txt")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["items"], [])

    def test_chunks_limit_zero(self):
        response = self.client.get("/api/knowledge-base/chunks?limit=0")
        self.assertEqual(response.status_code, 422)

    def test_chunks_skip_out_of_range(self):
        response = self.client.get("/api/knowledge-base/chunks?skip=9999")
        self.assertEqual(response.status_code, 200)

    def test_chunk_by_id_not_found(self):
        response = self.client.get("/api/knowledge-base/chunks/missing-chunk")
        self.assertEqual(response.status_code, 404)

    def test_hotspots_returns_list(self):
        response = self.client.get("/api/knowledge-base/hotspots")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_sources_returns_list(self):
        response = self.client.get("/api/knowledge-base/sources")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_config_returns_correct_structure(self):
        response = self.client.get("/api/knowledge-base/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("chunk_size", data)
        self.assertIn("chunk_overlap", data)

    def test_debug_search_returns_grouped_results(self):
        response = self.client.post("/api/knowledge-base/debug-search", json={"query": "test"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("vector_results", data)
        self.assertIn("bm25_results", data)
        self.assertIn("fused_results", data)

    # ── Metrics routes ──

    @patch("src.api.routes.metrics._LOG_DIR")
    def test_metrics_logs_dir_not_exist(self, mock_log_dir):
        mock_log_dir.exists.return_value = False
        response = self.client.get("/api/metrics/logs")
        self.assertEqual(response.status_code, 200)

    @patch("src.api.routes.metrics._LOG_DIR")
    def test_metrics_logs_empty(self, mock_log_dir):
        """Log directory with no matching files → empty summary payload."""
        mock_log_dir.exists.return_value = True
        mock_log_dir.glob.return_value = []
        response = self.client.get("/api/metrics/logs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "logs": [],
                "total_cost": 0.0,
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
            },
        )

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
