import unittest
from unittest.mock import patch

from src.api.models import DebugInfo
from src.api.routes.chat import _record_query_metrics


class ChatRouteMetricsTests(unittest.TestCase):
    @patch("src.api.routes.chat.log_query")
    def test_record_query_metrics_uses_debug_flags_instead_of_source_presence(self, mock_log_query):
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

        kwargs = mock_log_query.call_args.kwargs
        self.assertEqual(kwargs["retry_count"], 2)
        self.assertFalse(kwargs["used_web_search"])
        self.assertTrue(kwargs["used_rerank"])
        self.assertTrue(kwargs["used_rewrite"])
