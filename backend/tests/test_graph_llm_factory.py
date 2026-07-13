from unittest.mock import patch

import pytest
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


def test_get_llm_uses_fast_non_thinking_profile_for_standard_answers():
    with patch("src.graph.utils.require_siliconflow_api_key", return_value="sk-test"):
        with patch("src.graph.utils.ChatOpenAI") as mock_chat_openai:
            gu._get_llm(streaming=True, reasoning_mode="standard")

    _, kwargs = mock_chat_openai.call_args
    assert kwargs["max_tokens"] == 1024
    assert kwargs["request_timeout"] == 15
    assert kwargs["stream_chunk_timeout"] == 10
    assert kwargs["max_retries"] == 0
    assert kwargs["extra_body"] == {
        "enable_thinking": False,
        "thinking_budget": 128,
    }


def test_get_llm_reserves_full_reasoning_profile_for_deep_answers():
    with patch("src.graph.utils.require_siliconflow_api_key", return_value="sk-test"):
        with patch("src.graph.utils.ChatOpenAI") as mock_chat_openai:
            gu._get_llm(streaming=True, reasoning_mode="deep")

    _, kwargs = mock_chat_openai.call_args
    assert kwargs["max_tokens"] == 2048
    assert kwargs["request_timeout"] == 30
    assert kwargs["stream_chunk_timeout"] == 10
    assert kwargs["max_retries"] == 0
    assert kwargs["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 512,
        "reasoning_effort": "high",
    }


def test_get_llm_omits_v4_only_reasoning_effort_for_other_models():
    def runtime_setting(key, default=None):
        if key == "llm_model":
            return "Qwen/Qwen3-32B"
        return default

    with patch("src.graph.utils.get_runtime_setting", side_effect=runtime_setting):
        with patch("src.graph.utils.require_siliconflow_api_key", return_value="sk-test"):
            with patch("src.graph.utils.ChatOpenAI") as mock_chat_openai:
                gu._get_llm(streaming=True, reasoning_mode="deep")

    _, kwargs = mock_chat_openai.call_args
    assert kwargs["model"] == "Qwen/Qwen3-32B"
    assert kwargs["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 512,
    }


def test_get_llm_keeps_auxiliary_calls_short_and_non_thinking():
    with patch("src.graph.utils.require_siliconflow_api_key", return_value="sk-test"):
        with patch("src.graph.utils.ChatOpenAI") as mock_chat_openai:
            gu._get_llm(purpose="auxiliary")

    _, kwargs = mock_chat_openai.call_args
    assert kwargs["max_tokens"] == 256
    assert kwargs["request_timeout"] == 8
    assert kwargs["max_retries"] == 0
    assert kwargs["extra_body"] == {
        "enable_thinking": False,
        "thinking_budget": 128,
    }


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


def test_run_llm_text_closes_stream_when_total_deadline_expires():
    class ClosingIterator:
        def __init__(self):
            self.closed = False
            self._chunks = iter([AIMessageChunk(content="")])

        def __iter__(self):
            return self

        def __next__(self):
            return next(self._chunks)

        def close(self):
            self.closed = True

    class StreamingLLM:
        def __init__(self):
            self.iterator = ClosingIterator()

        def stream(self, _prompt):
            return self.iterator

    llm = StreamingLLM()
    with patch("src.graph.utils.time.monotonic", side_effect=[0.0, 16.0]):
        with pytest.raises(gu.LLMDeadlineExceeded):
            gu.run_llm_text(llm, "prompt", stream=True, deadline_seconds=15)

    assert llm.iterator.closed is True


def test_run_llm_text_rejects_partial_deep_answer_when_requested():
    class ClosingIterator:
        def __init__(self):
            self.closed = False
            self._chunks = iter([
                AIMessageChunk(content="partial"),
                AIMessageChunk(content=""),
            ])

        def __iter__(self):
            return self

        def __next__(self):
            return next(self._chunks)

        def close(self):
            self.closed = True

    class StreamingLLM:
        def __init__(self):
            self.iterator = ClosingIterator()

        def stream(self, _prompt):
            return self.iterator

    llm = StreamingLLM()
    with patch("src.graph.utils.time.monotonic", side_effect=[0.0, 1.0, 16.0]):
        with pytest.raises(gu.LLMDeadlineExceeded):
            gu.run_llm_text(
                llm,
                "prompt",
                stream=True,
                deadline_seconds=15,
                allow_partial_on_deadline=False,
            )

    assert llm.iterator.closed is True
