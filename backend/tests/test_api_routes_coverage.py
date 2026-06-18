"""Extended API route coverage — error paths for documents, KB, metrics, conversations."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.deps import get_knowledge_base
from src.api.main import app
from src import conversations


class FakeKnowledgeBase:
    """Minimal KB stub (reused from test_api_endpoints)."""

    def __init__(self):
        self._loaded = False
        self.all_docs = []

    def _ensure_loaded(self):
        if not self._loaded:
            from langchain_core.documents import Document
            self.all_docs = [
                Document(page_content="test", metadata={"source": "test.txt", "chunk_id": "test.txt:0:abc"}),
            ]
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
        return [{"chunk_id": "test.txt:0:abc", "source": "test.txt", "hits": 5, "content_preview": "test"}]

    def ingest_file(self, file_path, source_name=None):
        return 2

    def ingest_url(self, url):
        return 1

    def delete_source(self, source_name):
        if source_name == "existing.txt":
            return 2
        return 0

    def clear(self):
        self.all_docs = []


class APIRoutesCoverageTests(unittest.TestCase):
    """Error-path coverage for documents, knowledge_base, metrics routes."""

    @classmethod
    def setUpClass(cls):
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

    # ── Metrics routes ──

    @patch("src.api.routes.metrics._LOG_DIR")
    def test_metrics_logs_dir_not_exist(self, mock_log_dir):
        mock_log_dir.exists.return_value = False
        response = self.client.get("/api/metrics/logs")
        self.assertEqual(response.status_code, 200)

    @patch("src.api.routes.metrics._LOG_DIR")
    def test_metrics_logs_empty(self, mock_log_dir):
        """Log directory with no matching files → empty list."""
        mock_log_dir.exists.return_value = True
        mock_log_dir.iterdir.return_value = []
        response = self.client.get("/api/metrics/logs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
