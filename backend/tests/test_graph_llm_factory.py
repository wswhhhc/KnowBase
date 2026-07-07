from unittest.mock import patch

from src.graph import utils as gu


def test_get_llm_defaults_to_non_streaming_for_internal_nodes():
    with patch("src.graph.utils.require_siliconflow_api_key", return_value="sk-test"):
        with patch("src.graph.utils.ChatOpenAI") as mock_chat_openai:
            gu._get_llm()

    _, kwargs = mock_chat_openai.call_args
    assert kwargs["streaming"] is False


def test_get_llm_can_enable_streaming_for_answer_nodes():
    with patch("src.graph.utils.require_siliconflow_api_key", return_value="sk-test"):
        with patch("src.graph.utils.ChatOpenAI") as mock_chat_openai:
            gu._get_llm(streaming=True)

    _, kwargs = mock_chat_openai.call_args
    assert kwargs["streaming"] is True
