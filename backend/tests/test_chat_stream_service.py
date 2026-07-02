"""Focused unit tests for ChatStreamService without FastAPI/TestClient."""

from __future__ import annotations

import json
import time
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessageChunk

from src.api.chat_stream_service import ChatStreamService
from src.api.models import ChatRequest


class ChatStreamServiceTests(unittest.TestCase):
    @patch("src.api.chat_stream_service.run_query")
    def test_workspace_id_is_forwarded_to_run_query(self, mock_run_query):
        mock_run_query.return_value = iter([
            ("updates", {"finalize": {"evidence_level": "none", "outcome_category": "success"}}),
        ])
        body = ChatRequest(
            question="测试",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-alpha",
        )

        service = ChatStreamService(body, kb=object())
        list(service.run())

        _, kwargs = mock_run_query.call_args
        self.assertEqual(kwargs["workspace_id"], "ws-alpha")

    @patch("src.api.chat_persistence.replace_pin_state")
    @patch("src.api.chat_stream_service.record_query_metrics")
    @patch("src.api.chat_persistence.add_message", side_effect=[1, 2])
    @patch("src.api.chat_persistence.create_conversation", return_value={"id": "conv-1"})
    @patch("src.api.chat_persistence.generate_title", return_value="测试标题")
    @patch("src.api.chat_persistence.get_conversation_by_thread", return_value=None)
    @patch("src.api.chat_stream_service.run_query")
    def test_first_token_metrics_are_persisted_after_the_first_token(
        self,
        mock_run_query,
        _mock_get_conversation,
        _mock_generate_title,
        _mock_create_conversation,
        _mock_add_message,
        mock_record_query_metrics,
        _mock_replace_pin_state,
    ):
        """Metrics should distinguish first SSE event time from first token time."""

        def _delayed_sequence(**kwargs):
            yield ("updates", {"route_question": {"question_type": "knowledge_base"}})
            time.sleep(0.05)
            yield ("messages", (AIMessageChunk(content="你好"), {"langgraph_node": "generate_answer"}))
            yield ("updates", {"finalize": {"evidence_level": "high", "outcome_category": "success"}})

        mock_run_query.side_effect = _delayed_sequence
        body = ChatRequest(question="测试", web_search_enabled=False, search_strategy="balanced")
        service = ChatStreamService(body, kb=object())

        events = list(service.run())
        done_events = [event for event in events if event["event"] == "done"]

        self.assertEqual(len(done_events), 1)
        done_payload = json.loads(done_events[0]["data"])
        self.assertGreater(done_payload["elapsed_ms"], 0)
        self.assertEqual(done_payload["answer"], "你好")

        _, kwargs = mock_record_query_metrics.call_args
        self.assertLess(kwargs["ttfb_ms"], kwargs["first_token_ms"])
        self.assertGreaterEqual(kwargs["first_token_ms"], 40)


if __name__ == "__main__":
    unittest.main()
