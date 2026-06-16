"""Tests for src.web_search — format_search_results."""
import unittest

from src.web_search import format_search_results


class FormatSearchResultsTests(unittest.TestCase):
    """Tests for format_search_results."""

    def test_standard_results(self):
        """Standard results include title, url, content and source label."""
        results = [
            {"title": "测试标题", "url": "https://example.com", "content": "测试内容", "score": 0.9},
        ]
        output = format_search_results(results)
        self.assertIn("测试标题", output)
        self.assertIn("https://example.com", output)
        self.assertIn("测试内容", output)
        self.assertIn("[网络来源 1]", output)

    def test_multiple_results_numbered(self):
        """Multiple results are numbered correctly."""
        results = [
            {"title": "A", "url": "https://a.com", "content": "AAA", "score": 0.9},
            {"title": "B", "url": "https://b.com", "content": "BBB", "score": 0.8},
        ]
        output = format_search_results(results)
        self.assertIn("[网络来源 1]", output)
        self.assertIn("[网络来源 2]", output)

    def test_empty_results_returns_empty_string(self):
        """Empty results list returns empty string."""
        self.assertEqual(format_search_results([]), "")

    def test_result_missing_fields(self):
        """Results with missing fields still produce output with empty placeholders."""
        results = [
            {"title": "", "url": "", "content": "", "score": 0.0},
        ]
        output = format_search_results(results)
        self.assertIn("[网络来源 1]", output)

    def test_special_chars(self):
        """Special characters in content are preserved."""
        results = [
            {"title": "a & b < c > d", "url": "https://x.com/?a=1&b=2", "content": "line1\nline2", "score": 0.5},
        ]
        output = format_search_results(results)
        self.assertIn("&", output)
        self.assertIn("<", output)
        self.assertIn(">", output)
        self.assertIn("line1", output)
        self.assertIn("line2", output)


if __name__ == "__main__":
    unittest.main()
