"""Coverage tests for src.web_search — web_search() function with TavilyClient mock."""

import unittest
from unittest.mock import MagicMock, patch

from src import web_search as ws


class WebSearchCoverageTests(unittest.TestCase):
    """Tests for web_search() — the function that calls Tavily API."""

    @patch("src.web_search._is_configured_api_key", return_value=False)
    def test_no_api_key_returns_empty(self, _mock_key):
        results, error = ws.web_search("test query")
        self.assertEqual(results, [])
        self.assertIn("未配置", error)

    @patch("src.web_search._is_configured_api_key", return_value=True)
    @patch("tavily.TavilyClient")
    def test_successful_search_returns_results(self, mock_client_class, _mock_key):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {"title": "Result 1", "url": "https://ex.com/1", "content": "Content 1", "score": 0.9},
                {"title": "Result 2", "url": "https://ex.com/2", "content": "Content 2", "score": 0.8},
            ]
        }

        results, error = ws.web_search("test query", max_results=3)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Result 1")
        self.assertEqual(results[1]["url"], "https://ex.com/2")
        self.assertEqual(error, "")
        mock_client.search.assert_called_once_with(
            query="test query",
            search_depth="advanced",
            max_results=3,
            include_answer=True,
        )

    @patch("src.web_search._is_configured_api_key", return_value=True)
    @patch("tavily.TavilyClient")
    def test_missing_fields_use_defaults(self, mock_client_class, _mock_key):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {"title": "T", "content": "C"},  # missing url, score
            ]
        }

        results, error = ws.web_search("q")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "T")
        self.assertEqual(results[0]["url"], "")
        self.assertEqual(results[0]["content"], "C")
        self.assertEqual(results[0]["score"], 0.0)

    @patch("src.web_search._is_configured_api_key", return_value=True)
    @patch("tavily.TavilyClient")
    def test_api_exception_returns_error(self, mock_client_class, _mock_key):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.side_effect = RuntimeError("API timeout")

        results, error = ws.web_search("test query")

        self.assertEqual(results, [])
        self.assertIn("联网搜索失败", error)
        self.assertIn("API timeout", error)


class FormatSearchResultsCoverageTests(unittest.TestCase):
    """Additional coverage for format_search_results."""

    def test_very_long_content(self):
        results = [
            {"title": "T", "url": "https://x.com", "content": "A" * 10000, "score": 0.9},
        ]
        output = ws.format_search_results(results)
        # Content should be included, though not truncated by format_search_results
        self.assertIn("A" * 100, output)

    def test_none_in_fields(self):
        results = [
            {"title": None, "url": None, "content": None},
        ]
        output = ws.format_search_results(results)
        self.assertIn("[网络来源 1]", output)


if __name__ == "__main__":
    unittest.main()
