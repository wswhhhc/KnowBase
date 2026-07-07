"""Rate limit coverage for chat streaming and document imports."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.api.main import app
from src.api.rate_limit import InMemoryRateLimiter, RedisRateLimiter
from tests.helpers import setup_test_env, teardown_test_env


class FakeRedis:
    def __init__(self):
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.expires: dict[str, int] = {}

    def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        bucket = self.sorted_sets.setdefault(key, {})
        for member, score in list(bucket.items()):
            if min_score <= score <= max_score:
                bucket.pop(member, None)

    def zcard(self, key: str) -> int:
        return len(self.sorted_sets.setdefault(key, {}))

    def zrange(self, key: str, start: int, end: int, *, withscores: bool = False):
        items = sorted(self.sorted_sets.setdefault(key, {}).items(), key=lambda item: item[1])
        selected = items[start:end + 1 if end >= 0 else None]
        if withscores:
            return selected
        return [member for member, _score in selected]

    def zadd(self, key: str, mapping: dict[str, float]):
        self.sorted_sets.setdefault(key, {}).update(mapping)

    def expire(self, key: str, seconds: int):
        self.expires[key] = seconds

    def scan_iter(self, *, match: str):
        prefix = match.removesuffix("*")
        for key in list(self.sorted_sets):
            if key.startswith(prefix):
                yield key

    def delete(self, *keys: str):
        for key in keys:
            self.sorted_sets.pop(key, None)
            self.expires.pop(key, None)


class FailingRedis:
    def zremrangebyscore(self, *_args, **_kwargs):
        raise RuntimeError("redis unavailable")


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
        queued_job = {
            "id": "job-upload-rate-limit",
            "job_type": "ingest_file",
            "status": "queued",
            "created_by_user_id": None,
            "workspace_id": "",
            "progress": {"phase": "queued", "percent": 0},
            "error": "",
            "attempts": 0,
            "created_at": "2026-07-06T00:00:00+00:00",
            "updated_at": "2026-07-06T00:00:00+00:00",
            "started_at": None,
            "finished_at": None,
        }
        with patch("src.api.rate_limit.get_runtime_setting", side_effect=lambda key, default=None: 1 if key == "document_import_rate_limit_per_minute" else default):
            with patch("src.api.routes.documents.enqueue_tracked_job", return_value=queued_job):
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

        with patch("src.api.deps.settings.jwt_secret", ""):
            with patch("src.api.deps.get_runtime_setting", side_effect=_runtime_setting):
                with patch("src.api.rate_limit.get_runtime_setting", side_effect=_runtime_setting):
                    response = self.client.post(
                        "/api/chat/stream",
                        json={"question": "测试", "web_search_enabled": False, "search_strategy": "balanced"},
                        headers={"Authorization": "Bearer wrong-key"},
                    )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or missing API key")

    def test_redis_rate_limiter_uses_shared_sorted_set_bucket(self):
        redis = FakeRedis()
        limiter = RedisRateLimiter(redis_client=redis, key_prefix="test-rate")

        first = limiter.hit("chat:token:abc", limit=2, window_seconds=60, now=100.0)
        second = limiter.hit("chat:token:abc", limit=2, window_seconds=60, now=101.0)
        third = limiter.hit("chat:token:abc", limit=2, window_seconds=60, now=102.0)

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertEqual(third, 58)
        self.assertEqual(redis.expires["test-rate:chat:token:abc"], 120)

        after_window = limiter.hit("chat:token:abc", limit=2, window_seconds=60, now=161.0)
        self.assertIsNone(after_window)

    def test_redis_rate_limiter_falls_back_to_memory_when_redis_is_unavailable(self):
        limiter = RedisRateLimiter(
            redis_client=FailingRedis(),
            fallback=InMemoryRateLimiter(),
        )

        first = limiter.hit("document:ip:127.0.0.1", limit=1, window_seconds=60, now=200.0)
        second = limiter.hit("document:ip:127.0.0.1", limit=1, window_seconds=60, now=201.0)

        self.assertIsNone(first)
        self.assertEqual(second, 59)
