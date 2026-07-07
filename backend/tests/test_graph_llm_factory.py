from unittest.mock import patch

from langchain_core.messages import AIMessageChunk

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


def test_run_llm_text_calls_token_callback_while_streaming():
    class StreamingLLM:
        def stream(self, _prompt):
            yield AIMessageChunk(content="你")
            yield AIMessageChunk(content="好")

    tokens: list[str] = []

    answer, usage = gu.run_llm_text(
        StreamingLLM(),
        "prompt",
        stream=True,
        token_callback=tokens.append,
    )

    assert answer == "你好"
    assert tokens == ["你", "好"]
    assert usage == {}
