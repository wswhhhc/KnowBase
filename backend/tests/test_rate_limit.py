"""Rate limit coverage for chat streaming and document imports."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.api.main import app
from tests.helpers import setup_test_env, teardown_test_env


class RateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_kb, cls.client, cls.tmp_dir, cls.orig_db, cls.patchers = setup_test_env()

    @classmethod
    def tearDownClass(cls):
        teardown_test_env(cls.tmp_dir, cls.orig_db, cls.patchers)

    def setUp(self):
        app.state.rate_limiter.clear()

    def tearDown(self):
        app.state.rate_limiter.clear()

    def test_chat_stream_returns_429_after_limit(self):
        with patch("src.api.rate_limit.get_runtime_setting", side_effect=lambda key, default=None: 1 if key == "chat_stream_rate_limit_per_minute" else default):
            first = self.client.post(
                "/api/chat/stream",
                json={"question": "第一次", "web_search_enabled": False, "search_strategy": "balanced"},
            )
            second = self.client.post(
                "/api/chat/stream",
                json={"question": "第二次", "web_search_enabled": False, "search_strategy": "balanced"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn("请在", second.json()["detail"])
        self.assertGreaterEqual(int(second.headers["Retry-After"]), 1)
        self.assertLessEqual(int(second.headers["Retry-After"]), 60)

    def test_document_upload_and_url_import_share_the_same_rate_limit_bucket(self):
        with patch("src.api.rate_limit.get_runtime_setting", side_effect=lambda key, default=None: 1 if key == "document_import_rate_limit_per_minute" else default):
            first = self.client.post(
                "/api/documents/upload",
                files={"file": ("fresh.txt", b"hello world", "text/plain")},
            )
            second = self.client.post(
                "/api/documents/ingest-url",
                json={"url": "https://example.com/page"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn("请求过于频繁", second.json()["detail"])

    def test_invalid_api_key_still_returns_401_before_rate_limit(self):
        def _runtime_setting(key, default=None):
            if key == "api_key":
                return "test-api-key"
            if key == "chat_stream_rate_limit_per_minute":
                return 0
            return default

        with patch("src.api.deps.get_runtime_setting", side_effect=_runtime_setting):
            with patch("src.api.rate_limit.get_runtime_setting", side_effect=_runtime_setting):
                response = self.client.post(
                    "/api/chat/stream",
                    json={"question": "测试", "web_search_enabled": False, "search_strategy": "balanced"},
                    headers={"Authorization": "Bearer wrong-key"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or missing API key")
