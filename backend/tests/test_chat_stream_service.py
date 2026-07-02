"""Focused unit tests for ChatStreamService without FastAPI/TestClient."""

from __future__ import annotations

import json
import time
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AIMessageChunk

from src.api.chat_stream_service import ChatStreamService
from src.api.models import ChatRequest
from src.rag.models import RetrievalResult


class WorkspaceScopedGraphKB:
    def __init__(self):
        self.vector_store = type(
            "VectorStore",
            (),
            {"get": lambda *_args, **_kwargs: {"ids": [], "documents": [], "metadatas": []}},
        )()
        self.docs = {
            "ws-alpha": Document(
                page_content="alpha workspace answer",
                metadata={
                    "source": "alpha.txt",
                    "chunk_id": "ws-alpha::alpha.txt:0:aaa",
                    "chunk_index": 0,
                    "workspace_id": "ws-alpha",
                },
            ),
            "ws-beta": Document(
                page_content="beta workspace answer",
                metadata={
                    "source": "beta.txt",
                    "chunk_id": "ws-beta::beta.txt:0:bbb",
                    "chunk_index": 0,
                    "workspace_id": "ws-beta",
                },
            ),
        }

    def hybrid_search(self, _query, k, score_threshold=None, filter=None, workspace_id=None):
        doc = self.docs.get(workspace_id or "")
        if doc is None:
            return []
        return [
            RetrievalResult(
                chunk_id=doc.metadata["chunk_id"],
                document=doc,
                score=0.9,
            )
        ][:k]

    def get_neighbor_chunks(self, chunk_id, window=1, workspace_id=None):
        doc = next((item for item in self.docs.values() if item.metadata["chunk_id"] == chunk_id), None)
        if doc is None:
            return []
        if doc.metadata.get("workspace_id", "") != (workspace_id or ""):
            return []
        return [doc]


def _route_kb(_state):
    return {"question_type": "knowledge_base", "search_filter": {}}


def _generate_answer_from_sources(state):
    sources = state.get("sources", [])
    answer = sources[0]["content"] if sources else "no answer"
    return {"answer": answer, "sources": sources}


def _accept_answer(state):
    answer = state.get("answer", "")
    return {
        "quality_ok": True,
        "quality_reason": "skip",
        "retry_strategy": "none",
        "messages": [AIMessage(content=answer)] if answer else [],
    }


class ChatStreamServiceTests(unittest.TestCase):
    @patch("src.api.chat_stream_service.run_query")
    def test_workspace_id_is_forwarded_to_run_query(self, mock_run_query):
        mock_run_query.return_value = iter([
            ("updates", {"finalize": {"evidence_level": "none", "outcome_category": "success"}}),
        ])
        body = ChatRequest(
            question="测试",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-alpha",
        )

        service = ChatStreamService(body, kb=object())
        list(service.run())

        _, kwargs = mock_run_query.call_args
        self.assertEqual(kwargs["workspace_id"], "ws-alpha")

    @patch("src.api.chat_stream_service.get_conversation_by_thread")
    @patch("src.api.chat_stream_service.run_query")
    def test_existing_thread_workspace_overrides_request_workspace(
        self,
        mock_run_query,
        mock_get_conversation_by_thread,
    ):
        mock_get_conversation_by_thread.return_value = {
            "id": "conv-1",
            "thread_id": "thread-1",
            "workspace_id": "ws-alpha",
        }
        mock_run_query.return_value = iter([
            ("updates", {"finalize": {"evidence_level": "none", "outcome_category": "success"}}),
        ])
        body = ChatRequest(
            question="测试",
            thread_id="thread-1",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-beta",
        )

        service = ChatStreamService(body, kb=object())
        list(service.run())

        _, kwargs = mock_run_query.call_args
        self.assertEqual(kwargs["workspace_id"], "ws-alpha")

    @patch("src.api.chat_persistence.replace_pin_state")
    @patch("src.api.chat_stream_service.record_query_metrics")
    @patch("src.api.chat_persistence.add_message", side_effect=[1, 2])
    @patch("src.api.chat_persistence.create_conversation", return_value={"id": "conv-1"})
    @patch("src.api.chat_persistence.generate_title", return_value="测试标题")
    @patch("src.api.chat_persistence.get_conversation_by_thread", return_value=None)
    @patch("src.api.chat_stream_service.run_query")
    def test_first_token_metrics_are_persisted_after_the_first_token(
        self,
        mock_run_query,
        _mock_get_conversation,
        _mock_generate_title,
        _mock_create_conversation,
        _mock_add_message,
        mock_record_query_metrics,
        _mock_replace_pin_state,
    ):
        """Metrics should distinguish first SSE event time from first token time."""

        def _delayed_sequence(**kwargs):
            yield ("updates", {"route_question": {"question_type": "knowledge_base"}})
            time.sleep(0.05)
            yield ("messages", (AIMessageChunk(content="你好"), {"langgraph_node": "generate_answer"}))
            yield ("updates", {"finalize": {"evidence_level": "high", "outcome_category": "success"}})

        mock_run_query.side_effect = _delayed_sequence
        body = ChatRequest(question="测试", web_search_enabled=False, search_strategy="balanced")
        service = ChatStreamService(body, kb=object())

        events = list(service.run())
        done_events = [event for event in events if event["event"] == "done"]

        self.assertEqual(len(done_events), 1)
        done_payload = json.loads(done_events[0]["data"])
        self.assertGreater(done_payload["elapsed_ms"], 0)
        self.assertEqual(done_payload["answer"], "你好")

        _, kwargs = mock_record_query_metrics.call_args
        self.assertLess(kwargs["ttfb_ms"], kwargs["first_token_ms"])
        self.assertGreaterEqual(kwargs["first_token_ms"], 40)

    @patch.object(ChatStreamService, "_persist", return_value=("conv-1", 2))
    @patch("src.graph.nodes.check_quality", side_effect=_accept_answer)
    @patch("src.graph.nodes.generate_answer", side_effect=_generate_answer_from_sources)
    @patch("src.graph.graph.route_question", side_effect=_route_kb)
    def test_sse_payloads_only_include_active_workspace_sources(
        self,
        _mock_route_question,
        _mock_generate_answer,
        _mock_check_quality,
        _mock_persist,
    ):
        body = ChatRequest(
            question="workspace answer",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-alpha",
        )
        service = ChatStreamService(body, kb=WorkspaceScopedGraphKB())

        events = list(service.run())
        debug_payload = json.loads(next(event["data"] for event in events if event["event"] == "debug"))
        sources_payload = json.loads(next(event["data"] for event in events if event["event"] == "sources"))
        done_payload = json.loads(next(event["data"] for event in events if event["event"] == "done"))

        self.assertEqual(
            [source["chunk_id"] for source in debug_payload["context_sources"]],
            ["ws-alpha::alpha.txt:0:aaa"],
        )
        self.assertEqual(
            [source["chunk_id"] for source in sources_payload["sources"]],
            ["ws-alpha::alpha.txt:0:aaa"],
        )
        self.assertEqual(
            [source["chunk_id"] for source in done_payload["sources"]],
            ["ws-alpha::alpha.txt:0:aaa"],
        )
        self.assertNotIn("ws-beta::beta.txt:0:bbb", json.dumps(done_payload, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
