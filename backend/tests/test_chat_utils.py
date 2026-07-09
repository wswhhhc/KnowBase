"""Tests for chat route helper utilities."""

import unittest
from unittest.mock import patch

from src.chat_utils import generate_suggested_questions, generate_title


class GenerateTitleTests(unittest.TestCase):
    def test_generate_title_without_api_key_skips_llm(self):
        question = "这是一个很长的问题标题，用于测试没有 key 时的回退行为"
        with patch("src.config.runtime_overrides.get_runtime_setting", return_value=""), patch(
            "src.chat_utils.ChatPromptTemplate.from_messages"
        ) as mock_prompt, patch("langchain_openai.ChatOpenAI") as mock_chat_openai:
            title = generate_title(question)

        self.assertEqual(title, question[:30])
        mock_chat_openai.assert_not_called()
        mock_prompt.assert_not_called()

    def test_generate_title_auxiliary_llm_fails_fast(self):
        question = "请总结 LangChain 的用途"
        fake_key = "unit-live-api-key"
        with patch("src.chat_utils.get_runtime_setting", side_effect=lambda key, default=None: fake_key if key == "siliconflow_api_key" else default), patch(
            "src.chat_utils.require_siliconflow_api_key", return_value=fake_key
        ), patch("src.chat_utils.ChatOpenAI") as mock_chat_openai:
            mock_chat_openai.return_value.invoke.return_value.content = "LangChain 用途"

            title = generate_title(question)

        self.assertEqual(title, "LangChain 用途")
        _, kwargs = mock_chat_openai.call_args
        self.assertEqual(kwargs["timeout"], 15)
        self.assertEqual(kwargs["max_retries"], 0)

    def test_generate_suggested_questions_auxiliary_llm_fails_fast(self):
        docs_text = "LangChain 是一个用于构建大语言模型应用的框架。" * 5
        fake_key = "unit-live-api-key"
        with patch("src.chat_utils.get_runtime_setting", side_effect=lambda key, default=None: fake_key if key == "siliconflow_api_key" else default), patch(
            "src.chat_utils.require_siliconflow_api_key", return_value=fake_key
        ), patch("src.chat_utils.ChatOpenAI") as mock_chat_openai:
            mock_chat_openai.return_value.invoke.return_value.content = "LangChain 能做什么？\n它适合哪些场景？"

            questions = generate_suggested_questions(docs_text)

        self.assertEqual(questions, ["LangChain 能做什么？", "它适合哪些场景？"])
        _, kwargs = mock_chat_openai.call_args
        self.assertEqual(kwargs["timeout"], 15)
        self.assertEqual(kwargs["max_retries"], 0)


if __name__ == "__main__":
    unittest.main()
