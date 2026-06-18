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

    def test_assistant_msg_id_initialized_before_persistence(self):
        """Verify assistant_msg_id is set to 0 before the try block in event_generator."""
        import inspect
        from src.api.routes.chat import chat_stream
        source = inspect.getsource(chat_stream)

        # Verify assistant_msg_id = 0 appears before try: in the source
        lines = source.splitlines()
        assignment_line = None
        try_block_line = None
        for i, line in enumerate(lines):
            if "assistant_msg_id = 0" in line:
                assignment_line = i
            if "try:" in line and i > assignment_line if assignment_line is not None else False:
                try_block_line = i
                break

        self.assertIsNotNone(assignment_line, "assistant_msg_id = 0 must exist")
        self.assertIsNotNone(try_block_line, "try block after assignment must exist")
        self.assertLess(assignment_line, try_block_line,
                        "assistant_msg_id = 0 must be initialized BEFORE the try block")

