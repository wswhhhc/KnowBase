"""Extended tests for src.utils."""
import unittest
from unittest.mock import MagicMock, patch

from src.utils import (
    classify_error,
    extract_context_terms,
    format_chat_history,
    json_from_text,
    sanitize_upload_filename,
    save_uploaded_file,
    validate_upload,
)


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


class SaveUploadedFileTests(unittest.TestCase):
    """Tests for save_uploaded_file."""

    def _make_streamlit_file(self):
        """Create a mock Streamlit UploadedFile (has getbuffer)."""
        m = MagicMock(spec=["name", "size", "getbuffer"])
        m.getbuffer.return_value = b"file content bytes"
        m.name = "test.txt"
        m.size = 100
        return m

    def _make_fastapi_file(self):
        """Create a mock FastAPI UploadFile (has .file.read(), no getbuffer)."""
        m = MagicMock(spec=["file", "filename", "size"])
        m.file = MagicMock()
        m.file.read.side_effect = [b"fastapi content", b""]  # streaming read
        m.filename = "doc.md"
        m.size = 200
        return m

    def _make_unnamed_file(self, filename="virus.exe", size=100):
        """Create a mock file with no getbuffer (for validation-only tests)."""
        m = MagicMock(spec=["filename", "size", "file"])
        m.filename = filename
        m.size = size
        m.file = MagicMock()
        return m

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("src.utils.tempfile.gettempdir")
    def test_normal_save_streamlit_uploaded_file(self, mock_gettempdir, mock_open, mock_mkdir):
        """Normal save with Streamlit UploadedFile (has getbuffer)."""
        mock_gettempdir.return_value = "/tmp"

        mock_file = self._make_streamlit_file()
        file_path, source_name = save_uploaded_file(mock_file)

        self.assertIn("knowbase_uploads", file_path)
        self.assertTrue(file_path.endswith("test.txt"))
        self.assertEqual(source_name, "test.txt")

        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with(b"file content bytes")

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("src.utils.tempfile.gettempdir")
    def test_normal_save_fastapi_upload_file(self, mock_gettempdir, mock_open, mock_mkdir):
        """Normal save with FastAPI UploadFile (has .file.read())."""
        mock_gettempdir.return_value = "/tmp"

        mock_file = self._make_fastapi_file()
        file_path, source_name = save_uploaded_file(mock_file)

        self.assertIn("knowbase_uploads", file_path)
        self.assertTrue(file_path.endswith("doc.md"))
        self.assertEqual(source_name, "doc.md")

        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_with(b"fastapi content")

    def test_invalid_extension_raises_error(self):
        """Invalid file extension raises ValueError."""
        mock_file = self._make_unnamed_file(filename="virus.exe", size=100)

        with self.assertRaises(ValueError) as ctx:
            save_uploaded_file(mock_file)
        self.assertIn("仅支持", str(ctx.exception))

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("src.utils.tempfile.gettempdir")
    def test_oversized_file_raises_error(self, mock_gettempdir, mock_open, mock_mkdir):
        """Oversized file raises ValueError."""
        mock_gettempdir.return_value = "/tmp"

        mock_file = MagicMock(spec=["file", "filename", "size"])
        mock_file.filename = "large.txt"
        mock_file.size = 6 * 1024 * 1024
        mock_file.file = MagicMock()
        # First chunk exceeds limit
        mock_file.file.read.side_effect = [b"x" * (6 * 1024 * 1024), b""]

        with self.assertRaises(ValueError) as ctx:
            save_uploaded_file(mock_file)
        self.assertIn("不能超过", str(ctx.exception))


class FormatChatHistoryTests(unittest.TestCase):
    """Tests for format_chat_history."""

    def test_normal_user_assistant_pairs(self):
        """Normal user+assistant pairs produce correct output."""
        messages = [
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
            {"role": "user", "content": "问题2"},
            {"role": "assistant", "content": "回答2"},
        ]
        result = format_chat_history(messages)
        self.assertEqual(result, [("问题1", "回答1"), ("问题2", "回答2")])

    def test_orphan_assistant_skipped(self):
        """Orphan assistant message (no preceding user) is skipped."""
        messages = [
            {"role": "assistant", "content": "无前驱的回答"},
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
        ]
        result = format_chat_history(messages)
        self.assertEqual(result, [("问题1", "回答1")])

    def test_empty_list_returns_empty(self):
        """Empty list returns empty list."""
        self.assertEqual(format_chat_history([]), [])

    def test_user_without_following_assistant(self):
        """User message without following assistant is included with empty answer."""
        messages = [
            {"role": "user", "content": "只有问题"},
        ]
        result = format_chat_history(messages)
        self.assertEqual(result, [("只有问题", "")])

    def test_multiple_orphan_assistants(self):
        """Consecutive orphan assistant messages are all skipped."""
        messages = [
            {"role": "assistant", "content": "孤儿1"},
            {"role": "assistant", "content": "孤儿2"},
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": "回答"},
        ]
        result = format_chat_history(messages)
        self.assertEqual(result, [("问题", "回答")])


if __name__ == "__main__":
    unittest.main()
