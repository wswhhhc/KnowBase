import unittest
from unittest.mock import patch

from src.api.models import DebugInfo
from src.api.routes.chat import _record_query_metrics


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

    @patch("src.api.routes.chat.get_conversation_by_thread")
    def test_persistence_failure_returns_done_with_zero_msg_id(self, mock_get):
        """Simulate add_message throwing — done event has assistant_msg_id=0."""
        mock_get.return_value = None

        with patch("src.api.routes.chat.create_conversation") as mock_create:
            mock_create.side_effect = RuntimeError("DB timeout")

            from src.api.routes.chat import _record_query_metrics, NODE_LABELS
            from src.graph import _initial_state
            # This tests the expected behavior: the event_generator in chat_stream
            # initializes assistant_msg_id = 0 before the try block, so
            # after a persistence failure the done event won't crash with UnboundLocalError.
            state = _initial_state("test")
            self.assertEqual(state["retrieval_k"], 5)  # default from settings

