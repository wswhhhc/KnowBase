"""SSE integration tests for /api/chat/stream — event types, field correctness, error paths."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.api.deps import get_knowledge_base
from src.api.main import app
from tests.helpers import FakeKnowledgeBase, setup_test_env, teardown_test_env


def _parse_sse_events(text: str) -> list[dict]:
    """Parse raw SSE text into a list of ``{event, data}`` dicts."""
    events = []
    current_event = "message"
    for line in text.splitlines():
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            try:
                parsed = json.loads(line[6:])
            except json.JSONDecodeError:
                parsed = line[6:]
            events.append({"event": current_event, "data": parsed})
            current_event = "message"
    return events


class ChatRouteSSEIntegrationTests(unittest.TestCase):
    """Full SSE event stream tests via TestClient + mock graph."""

    @classmethod
    def setUpClass(cls):
        cls.fake_kb, cls.client, cls.tmp_dir, cls.orig_db, cls.patchers = setup_test_env()
        # Remove the real run_query dependency — we inject a controlled sequence
        cls._run_query_patcher = patch("src.api.routes.chat.run_query")
        cls._mock_run_query = cls._run_query_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._run_query_patcher.stop()
        teardown_test_env(cls.tmp_dir, cls.orig_db, cls.patchers)

    def setUp(self):
        # Reset the mock between tests
        self._mock_run_query.reset_mock()

    def _post(self, **overrides: str | bool) -> str:
        """Post to /api/chat/stream and return raw SSE text."""
        body = {"question": "测试", "web_search_enabled": False, "search_strategy": "balanced", **overrides}
        resp = self.client.post("/api/chat/stream", json=body)
        self.assertEqual(resp.status_code, 200)
        return resp.text

    # -- Helpers to build mock graph events --
    @staticmethod
    def _make_run_query(*sequence):
        """Return a callable that ignores arguments and yields ``sequence``.

        ``run_query`` is called with (question, thread_id, knowledge_base, ...)
        keyword arguments, so ``side_effect`` must accept ``**kwargs``.
        """
        def _gen(**kwargs):
            yield from sequence
        return _gen

    # -- Tests --

    def test_node_event(self):
        """SSE node event includes label and cumulative nodes list."""
        self._mock_run_query.side_effect = self._make_run_query(
            ("updates", {"route_question": {"question_type": "knowledge_base"}}),
        )

        events = _parse_sse_events(self._post())
        node_events = [e for e in events if e["event"] == "node"]

        self.assertGreater(len(node_events), 0)
        self.assertEqual(node_events[0]["data"]["label"], "问题路由")
        self.assertEqual(node_events[0]["data"]["nodes"], ["问题路由"])

    def test_token_event(self):
        """SSE token event carries assistant text content."""
        from langchain_core.messages import AIMessageChunk

        self._mock_run_query.side_effect = self._make_run_query(
            ("messages", (AIMessageChunk(content="你好"), {"langgraph_node": "generate_answer"})),
            ("updates", {"finalize": {"evidence_level": "medium", "outcome_category": "success"}}),
        )

        events = _parse_sse_events(self._post())
        token_events = [e for e in events if e["event"] == "token"]

        self.assertGreater(len(token_events), 0)
        self.assertEqual(token_events[0]["data"]["text"], "你好")

    def test_debug_event(self):
        """SSE debug event carries DebugInfo structure."""
        self._mock_run_query.side_effect = self._make_run_query(
            ("updates", {"route_question": {"question_type": "knowledge_base"}}),
            ("updates", {"retrieve_docs": {"sources": ["doc1"]}}),
            ("updates", {"check_quality": {"quality_ok": True, "quality_reason": "pass"}}),
            ("updates", {"finalize": {"evidence_level": "high", "outcome_category": "success"}}),
        )

        events = _parse_sse_events(self._post())
        debug_events = [e for e in events if e["event"] == "debug"]

        self.assertEqual(len(debug_events), 1)
        debug = debug_events[0]["data"]
        self.assertIn("nodes", debug)
        self.assertIn("retrieval_k", debug)
        self.assertIn("quality_passed", debug)
        self.assertIn("used_rerank", debug)
        self.assertIn("used_rewrite", debug)

    def test_sources_event(self):
        """SSE sources event carries final source metadata."""
        self._mock_run_query.side_effect = self._make_run_query(
            ("updates", {"retrieve_docs": {"sources": [{"source": "doc.md", "content": "abc"}]}}),
            ("updates", {"finalize": {"evidence_level": "low", "outcome_category": "success"}}),
        )

        events = _parse_sse_events(self._post())
        src_events = [e for e in events if e["event"] == "sources"]

        self.assertEqual(len(src_events), 1)
        src = src_events[0]["data"]
        self.assertIn("sources", src)
        self.assertIn("quality_reason", src)
        self.assertIn("evidence_level", src)
        self.assertIn("outcome_category", src)

    def test_done_event_all_fields(self):
        """SSE done event includes all required fields."""
        from langchain_core.messages import AIMessageChunk

        self._mock_run_query.side_effect = self._make_run_query(
            ("messages", (AIMessageChunk(content="最终回答"), {"langgraph_node": "generate_answer"})),
            ("updates", {"finalize": {"evidence_level": "high", "outcome_category": "success"}}),
        )

        events = _parse_sse_events(self._post())
        done_events = [e for e in events if e["event"] == "done"]

        self.assertEqual(len(done_events), 1)
        done = done_events[0]["data"]
        self.assertIn("thread_id", done)
        self.assertIn("conv_id", done)
        self.assertIn("assistant_msg_id", done)
        self.assertIn("answer", done)
        self.assertIn("sources", done)
        self.assertIn("quality_reason", done)
        self.assertIn("evidence_level", done)
        self.assertIn("outcome_category", done)
        self.assertIn("elapsed_ms", done)
        self.assertGreaterEqual(done["elapsed_ms"], 0)

    def test_full_event_sequence(self):
        """Complete chat cycle produces node → token → debug → sources → done in order."""
        from langchain_core.messages import AIMessageChunk

        self._mock_run_query.side_effect = self._make_run_query(
            ("updates", {"route_question": {"question_type": "knowledge_base"}}),
            ("messages", (AIMessageChunk(content="你好，"), {"langgraph_node": "generate_answer"})),
            ("messages", (AIMessageChunk(content="我是助手。"), {"langgraph_node": "generate_answer"})),
            ("updates", {"retrieve_docs": {"sources": [{"source": "doc.md", "content": "info"}]}}),
            ("updates", {"finalize": {"evidence_level": "medium", "outcome_category": "success"}}),
        )

        events = _parse_sse_events(self._post())
        event_types = [e["event"] for e in events]

        self.assertIn("node", event_types)
        self.assertIn("token", event_types)
        self.assertIn("debug", event_types)
        self.assertIn("sources", event_types)
        self.assertIn("done", event_types)

        tail = event_types[-3:]
        self.assertIn("debug", tail)
        self.assertIn("sources", tail)
        self.assertEqual(tail[-1], "done")

    def test_error_event(self):
        """When run_query raises, SSE error event fires."""
        self._mock_run_query.side_effect = RuntimeError("模拟异常")

        events = _parse_sse_events(self._post())
        error_events = [e for e in events if e["event"] == "error"]

        self.assertGreater(len(error_events), 0)
        self.assertIn("模拟异常", str(error_events[0]["data"]))


if __name__ == "__main__":
    unittest.main()
