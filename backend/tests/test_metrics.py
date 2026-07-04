import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import metrics
from src.api.models import QueryLogEntry
from src.api.routes.metrics import _apply_debug_web_search_flags


class MetricsTests(unittest.TestCase):
    def test_clear_today_log_removes_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            log_file = log_dir / f"rag_{today}.jsonl"
            log_file.write_text("{}", encoding="utf-8")

            with patch("src.metrics._LOG_DIR", log_dir):
                removed = metrics.clear_today_log()

            self.assertTrue(removed)
            self.assertFalse(log_file.exists())

    def test_clear_today_log_returns_false_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)

            with patch("src.metrics._LOG_DIR", log_dir):
                removed = metrics.clear_today_log()

            self.assertFalse(removed)


class MetricsDashboardTests(unittest.TestCase):
    def test_quality_fail_rate_uses_recent_n_rows(self):
        df = pd.DataFrame(
            [
                {"timestamp": datetime(2026, 6, 14, 8, 0, tzinfo=UTC), "quality_ok": False},
                {"timestamp": datetime(2026, 6, 14, 8, 1, tzinfo=UTC), "quality_ok": False},
                {"timestamp": datetime(2026, 6, 14, 8, 2, tzinfo=UTC), "quality_ok": True},
                {"timestamp": datetime(2026, 6, 14, 8, 3, tzinfo=UTC), "quality_ok": True},
            ]
        )

        self.assertEqual(metrics.quality_fail_rate(df), 50.0)
        self.assertEqual(metrics.quality_fail_rate(df, recent_n=2), 0.0)
        self.assertEqual(metrics.quality_fail_rate(df, recent_n=3), 33.333333333333336)

    @patch("src.api.routes.metrics.message_repository.list_assistant_debug_pairs")
    def test_apply_debug_web_search_flags_overrides_stale_log_values(self, mock_pairs):
        records = [
            QueryLogEntry(
                timestamp="2026-06-15T08:00:00+00:00",
                thread_id="thread-1",
                question="重复问题",
                elapsed_ms=1000,
                retrieval_count=1,
                quality_ok=True,
                quality_reason="ok",
                used_web_search=True,
            ),
            QueryLogEntry(
                timestamp="2026-06-15T09:00:00+00:00",
                thread_id="thread-1",
                question="重复问题",
                elapsed_ms=1200,
                retrieval_count=1,
                quality_ok=True,
                quality_reason="ok",
                used_web_search=True,
            ),
        ]
        mock_pairs.return_value = [
            {
                "thread_id": "thread-1",
                "question": "重复问题",
                "debug_info": {"used_web_search": False},
                "created_at": "2026-06-15T08:00:01+00:00",
            },
            {
                "thread_id": "thread-1",
                "question": "重复问题",
                "debug_info": {"used_web_search": True},
                "created_at": "2026-06-15T09:00:01+00:00",
            },
        ]

        _apply_debug_web_search_flags(records)

        self.assertFalse(records[0].used_web_search)
        self.assertTrue(records[1].used_web_search)


if __name__ == "__main__":
    unittest.main()
