"""Extended tests for src.utils — json_from_text and classify_error."""
import unittest

from src.utils import classify_error, json_from_text


class JsonFromTextTests(unittest.TestCase):
    def test_pure_json_string(self):
        result = json_from_text('{"a": 1, "b": "hello"}')
        self.assertEqual(result, {"a": 1, "b": "hello"})

    def test_markdown_fenced_json(self):
        result = json_from_text(
            '```json\n{"quality_passed": true, "reason": "ok"}\n```'
        )
        self.assertEqual(result, {"quality_passed": True, "reason": "ok"})

    def test_markdown_fenced_without_language_tag(self):
        result = json_from_text(
            '```\n{"key": "value"}\n```'
        )
        self.assertEqual(result, {"key": "value"})

    def test_json_with_surrounding_text(self):
        result = json_from_text(
            'Here is the result:\n{"answer": 42}\nEnd.'
        )
        self.assertEqual(result, {"answer": 42})

    def test_no_json_brace_raises_error(self):
        with self.assertRaises(Exception):
            json_from_text("just some text without braces")

    def test_empty_string_raises_error(self):
        with self.assertRaises(Exception):
            json_from_text("")

    def test_nested_json_in_markdown(self):
        result = json_from_text(
            '```json\n{"outer": {"inner": [1, 2, 3]}}\n```'
        )
        self.assertEqual(result, {"outer": {"inner": [1, 2, 3]}})


class ClassifyErrorTests(unittest.TestCase):
    def test_authentication_error(self):
        title, suggestion = classify_error(Exception("invalid api_key"))
        self.assertIn("API Key", title)
        self.assertIn("配置", title)

    def test_auth_keyword_in_message(self):
        title, suggestion = classify_error(Exception("authentication failed: unauthorized"))
        self.assertIn("API Key", title)

    def test_rate_limit_error(self):
        title, suggestion = classify_error(Exception("rate limit exceeded"))
        self.assertIn("限流", title)

    def test_rate_limit_429(self):
        title, suggestion = classify_error(Exception("HTTP 429 Too Many Requests"))
        self.assertIn("限流", title)

    def test_too_many_requests(self):
        title, suggestion = classify_error(Exception("too many requests, try again later"))
        self.assertIn("限流", title)

    def test_timeout_error(self):
        title, suggestion = classify_error(Exception("request timed out"))
        self.assertIn("超时", title)

    def test_timeout_keyword(self):
        title, suggestion = classify_error(Exception("timeout: connection reset"))
        self.assertIn("超时", title)

    def test_unknown_error(self):
        title, suggestion = classify_error(Exception("something completely unexpected"))
        self.assertEqual(title, "未知错误")

    def test_model_not_found(self):
        title, suggestion = classify_error(Exception("model not found: gpt-5"))
        self.assertIn("模型", title)


if __name__ == "__main__":
    unittest.main()
