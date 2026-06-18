"""Chat route tests — metrics delegation and SSE persistence failure behavior."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.deps import get_knowledge_base
from src.api.main import app
from src.api.models import DebugInfo
from src.api.routes.chat import _record_query_metrics
from src import conversations


class ChatRouteMetricsTests(unittest.TestCase):
    @patch("src.api.routes.chat.record_query_metrics")
    def test_record_query_metrics_uses_debug_flags_instead_of_source_presence(self, mock_record):
        debug_info = DebugInfo(
            retry_count=2,
            used_web_search=False,
            used_rerank=True,
            used_rewrite=True,
        )

        _record_query_metrics(
            question="测试问题",
            thread_id="thread-1",
            final_sources=[{"source": "doc.md"}],
            final_quality_ok=True,
            final_quality="ok",
            elapsed=321,
            answer="测试回答",
            debug_info=debug_info,
        )

        kwargs = mock_record.call_args.kwargs
        self.assertEqual(kwargs["debug_info"].retry_count, 2)
        self.assertFalse(kwargs["debug_info"].used_web_search)
        self.assertTrue(kwargs["debug_info"].used_rerank)
        self.assertTrue(kwargs["debug_info"].used_rewrite)


class ChatRoutePersistenceFailureTests(unittest.TestCase):
    """If persistence throws, SSE done should still fire with assistant_msg_id=0."""

    @classmethod
    def setUpClass(cls):
        cls.patcher_api = patch("src.knowledge_base.require_siliconflow_api_key", return_value="sk-test")
        cls.patcher_chroma = patch("src.knowledge_base.Chroma")
        cls.patcher_emb = patch("src.knowledge_base.OpenAIEmbeddings")
        cls.patcher_api.start()
        cls.patcher_chroma.start()
        cls.patcher_emb.start()

        class FakeKB:
            def hybrid_search(self, *a, **kw): return []
            @staticmethod
            def get_neighbor_chunks(*a, **kw): return []
            def load_preset_documents(self): return 0
            def _ensure_loaded(self): pass

        cls.fake_kb = FakeKB()
        app.dependency_overrides[get_knowledge_base] = lambda: cls.fake_kb

        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._orig_db = conversations._DB_PATH
        conversations._DB_PATH = Path(cls._tmp_dir.name) / "conv.db"
        conversations.init_db()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        conversations._DB_PATH = cls._orig_db
        cls._tmp_dir.cleanup()
        app.dependency_overrides.clear()
        cls.patcher_emb.stop()
        cls.patcher_chroma.stop()
        cls.patcher_api.stop()

    def test_persistence_failure_done_has_zero_msg_id(self):
        """When add_message raises, SSE done event must contain assistant_msg_id=0."""
        with patch("src.api.routes.chat.add_message") as mock_add:
            mock_add.side_effect = RuntimeError("DB timeout")

            resp = self.client.post(
                "/api/chat/stream",
                json={"question": "测试", "web_search_enabled": False, "search_strategy": "balanced"},
            )
            self.assertEqual(resp.status_code, 200)

            # Parse SSE text, find the done event
            done_found = False
            for line in resp.text.splitlines():
                if line.startswith("data: ") and '"assistant_msg_id"' in line:
                    data = json.loads(line[6:])
                    self.assertEqual(data["assistant_msg_id"], 0,
                                     "assistant_msg_id must be 0 when persistence fails")
                    self.assertIn("thread_id", data)
                    self.assertIn("answer", data)
                    done_found = True
                    break

            self.assertTrue(done_found, "SSE done event with assistant_msg_id must be present")
