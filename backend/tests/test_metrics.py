import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import metrics


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


if __name__ == "__main__":
    unittest.main()
