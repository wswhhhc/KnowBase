"""Extended metrics tests — log_query JSONL format, truncation, quality_fail_rate edges."""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import metrics
from src.metrics import quality_fail_rate


class LogQueryFormatTests(unittest.TestCase):
    """Tests for log_query — JSONL writing and truncation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _patch_log_dir(self):
        return patch("src.metrics._LOG_DIR", self.log_dir)

    def test_log_query_writes_valid_jsonl(self):
        with self._patch_log_dir():
            metrics.log_query(
                question="测试问题",
                thread_id="thread-1",
                question_type="knowledge_base",
                retrieval_count=3,
                retry_count=0,
                quality_ok=True,
                quality_reason="ok",
                source_count=2,
                elapsed_ms=1500,
                answer="这是回答",
            )

        files = list(self.log_dir.iterdir())
        self.assertEqual(len(files), 1)
        lines = files[0].read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["question"], "测试问题")
        self.assertEqual(record["thread_id"], "thread-1")
        self.assertTrue(record["quality_ok"])

    def test_log_query_truncates_question(self):
        with self._patch_log_dir():
            metrics.log_query(
                question="A" * 200,
                thread_id="t",
                question_type="knowledge_base",
                retrieval_count=0,
                retry_count=0,
                quality_ok=True,
                quality_reason="ok",
                source_count=0,
                elapsed_ms=0,
                answer="",
            )

        files = list(self.log_dir.iterdir())
        record = json.loads(files[0].read_text(encoding="utf-8").strip())
        self.assertEqual(len(record["question"]), 100)

    def test_log_query_truncates_answer_preview(self):
        with self._patch_log_dir():
            metrics.log_query(
                question="q",
                thread_id="t",
                question_type="knowledge_base",
                retrieval_count=0,
                retry_count=0,
                quality_ok=True,
                quality_reason="ok",
                source_count=0,
                elapsed_ms=0,
                answer="B" * 500,
            )

        files = list(self.log_dir.iterdir())
        record = json.loads(files[0].read_text(encoding="utf-8").strip())
        self.assertEqual(len(record["answer_preview"]), 200)

    def test_log_query_with_all_fields(self):
        with self._patch_log_dir():
            metrics.log_query(
                question="q",
                thread_id="t",
                question_type="knowledge_base",
                retrieval_count=5,
                retry_count=1,
                quality_ok=False,
                quality_reason="bad",
                source_count=0,
                elapsed_ms=2000,
                answer="ans",
                error="timeout",
                token_count=150,
                used_web_search=True,
                used_rerank=False,
                used_rewrite=True,
            )

        files = list(self.log_dir.iterdir())
        record = json.loads(files[0].read_text(encoding="utf-8").strip())
        self.assertTrue(record["used_web_search"])
        self.assertFalse(record["used_rerank"])
        self.assertTrue(record["used_rewrite"])
        self.assertEqual(record["token_count"], 150)
        self.assertEqual(record["error"], "timeout")


class QualityFailRateExtendedTests(unittest.TestCase):
    """Extended quality_fail_rate edge cases."""

    def test_empty_dataframe_returns_0(self):
        df = pd.DataFrame()
        self.assertEqual(quality_fail_rate(df), 0.0)

    def test_missing_quality_ok_column_returns_0(self):
        df = pd.DataFrame({"other_col": [1, 2]})
        self.assertEqual(quality_fail_rate(df), 0.0)

    def test_all_quality_ok_returns_0(self):
        df = pd.DataFrame(
            {"quality_ok": [True, True, True], "timestamp": [datetime.now(UTC)] * 3}
        )
        self.assertEqual(quality_fail_rate(df), 0.0)

    def test_all_quality_fail_returns_100(self):
        df = pd.DataFrame(
            {"quality_ok": [False, False], "timestamp": [datetime.now(UTC)] * 2}
        )
        self.assertEqual(quality_fail_rate(df), 100.0)

    def test_recent_n_empty_returns_0(self):
        df = pd.DataFrame(
            {"quality_ok": [True], "timestamp": [datetime.now(UTC)]}
        )
        self.assertEqual(quality_fail_rate(df, recent_n=0), 0.0)


class ClearTodayLogExtendedTests(unittest.TestCase):
    """Extended clear_today_log edge cases."""

    def test_log_dir_does_not_exist(self):
        with patch("src.metrics._LOG_DIR", Path("/nonexistent/path/xyz")):
            result = metrics.clear_today_log()
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
