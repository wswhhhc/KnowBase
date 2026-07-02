"""Tests for chat route helper utilities."""

import unittest
from unittest.mock import patch

from src.chat_utils import generate_title


class GenerateTitleTests(unittest.TestCase):
    def test_generate_title_without_api_key_skips_llm(self):
        question = "这是一个很长的问题标题，用于测试没有 key 时的回退行为"
        with patch("src.config.settings.settings.siliconflow_api_key", ""), patch(
            "src.chat_utils.ChatPromptTemplate.from_messages"
        ) as mock_prompt, patch("langchain_openai.ChatOpenAI") as mock_chat_openai:
            title = generate_title(question)

        self.assertEqual(title, question[:30])
        mock_chat_openai.assert_not_called()
        mock_prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
