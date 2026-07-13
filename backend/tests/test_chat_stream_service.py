"""Focused unit tests for ChatStreamService without FastAPI/TestClient."""

from __future__ import annotations

import json
import time
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AIMessageChunk

from src.api.chat_persistence import ConversationWorkspaceMismatchError
from src.api.chat_stream_service import ChatStreamService
from src.api.models import ChatRequest
from src.rag.models import KBChunk
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


class E2EFakeChatKB:
    def list_chunks(self, *, workspace_id: str = "", source: str = "", search: str = "", skip: int = 0, limit: int = 50):
        return 1, [
            KBChunk(
                source="e2e-note.md",
                chunk_index=0,
                chunk_id=f"{workspace_id}::e2e-note.md:0:abc" if workspace_id else "e2e-note.md:0:abc",
                content="contextual wrapper",
                original_content="E2E 导入资料说明 KnowBase 支持团队问答。",
            )
        ]


class RefreshableKB:
    def __init__(self):
        self.refresh_calls = 0

    def refresh_from_persisted_store(self):
        self.refresh_calls += 1


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
    @patch.object(ChatStreamService, "_persist", return_value=("conv-1", 2))
    @patch("src.api.chat_stream_service.run_query")
    def test_workspace_id_is_forwarded_to_run_query(self, mock_run_query, _mock_persist):
        mock_run_query.return_value = iter([
            ("updates", {"finalize": {"evidence_level": "none", "outcome_category": "success"}}),
        ])
        body = ChatRequest(
            question="测试",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-alpha",
        )

        service = ChatStreamService(body, kb=object(), authorized_workspace_id="ws-alpha")
        list(service.run())

        _, kwargs = mock_run_query.call_args
        self.assertEqual(kwargs["workspace_id"], "ws-alpha")

    @patch.object(ChatStreamService, "_persist", return_value=("conv-1", 2))
    @patch("src.api.chat_stream_service.settings")
    @patch("src.api.chat_stream_service.run_query")
    def test_real_chat_refreshes_kb_before_running_graph(
        self,
        mock_run_query,
        mock_settings,
        _mock_persist,
    ):
        mock_settings.e2e_fake_ai = False
        kb = RefreshableKB()

        def _run_query(**_kwargs):
            self.assertEqual(kb.refresh_calls, 1)
            return iter([
                ("updates", {"finalize": {"evidence_level": "none", "outcome_category": "success"}}),
            ])

        mock_run_query.side_effect = _run_query
        body = ChatRequest(
            question="测试",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-alpha",
        )

        list(ChatStreamService(body, kb=kb, authorized_workspace_id=body.workspace_id).run())

        self.assertEqual(kb.refresh_calls, 1)

    @patch.object(ChatStreamService, "_persist", return_value=("conv-1", 2))
    @patch("src.api.chat_stream_service.run_query")
    def test_manual_token_callback_events_are_drained(self, mock_run_query, _mock_persist):
        def _run_query(**kwargs):
            kwargs["token_callback"]("实时")
            return iter([
                ("updates", {"finalize": {"evidence_level": "high", "outcome_category": "success"}}),
            ])

        mock_run_query.side_effect = _run_query
        body = ChatRequest(question="测试", web_search_enabled=False, search_strategy="balanced")

        events = list(ChatStreamService(body, kb=object(), authorized_workspace_id=body.workspace_id).run())
        token_texts = [
            json.loads(event["data"])["text"]
            for event in events
            if event["event"] == "token"
        ]

        self.assertEqual(token_texts, ["实时"])

    @patch(
        "src.api.chat_stream_service.persist_conversation_turn",
        side_effect=ConversationWorkspaceMismatchError("会话与当前工作区不匹配"),
    )
    @patch("src.api.chat_stream_service.run_query")
    def test_workspace_race_emits_error_without_done(
        self,
        mock_run_query,
        _mock_persist_conversation_turn,
    ):
        mock_run_query.return_value = iter([
            ("updates", {"finalize": {"evidence_level": "none", "outcome_category": "success"}}),
        ])
        body = ChatRequest(
            question="测试",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-alpha",
        )

        events = list(
            ChatStreamService(
                body,
                kb=object(),
                authorized_workspace_id=body.workspace_id,
            ).run()
        )

        self.assertNotIn("done", [event["event"] for event in events])
        error = next(event for event in events if event["event"] == "error")
        self.assertIn("工作区", json.loads(error["data"])["message"])

    @patch(
        "src.api.chat_persistence.conversation_store.persist_conversation_turn",
        return_value=("conv-1", 2),
    )
    @patch("src.api.chat_stream_service.record_query_metrics")
    @patch("src.api.chat_persistence.generate_title", return_value="测试标题")
    @patch(
        "src.api.chat_persistence.conversation_store.get_conversation_by_thread",
        return_value=None,
    )
    @patch("src.api.chat_stream_service.run_query")
    def test_first_token_metrics_are_persisted_after_the_first_token(
        self,
        mock_run_query,
        _mock_get_conversation,
        _mock_generate_title,
        mock_record_query_metrics,
        _mock_persist_conversation_turn,
    ):
        """Metrics should distinguish first SSE event time from first token time."""

        def _delayed_sequence(**kwargs):
            yield ("updates", {"route_question": {"question_type": "knowledge_base"}})
            time.sleep(0.05)
            yield ("messages", (AIMessageChunk(content="你好"), {"langgraph_node": "generate_answer"}))
            yield ("updates", {"finalize": {"evidence_level": "high", "outcome_category": "success"}})

        mock_run_query.side_effect = _delayed_sequence
        body = ChatRequest(question="测试", web_search_enabled=False, search_strategy="balanced")
        service = ChatStreamService(body, kb=object(), authorized_workspace_id=body.workspace_id)

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
    @patch("src.api.chat_stream_service.run_query")
    def test_only_visible_answer_nodes_emit_token_events(
        self,
        mock_run_query,
        _mock_persist,
    ):
        mock_run_query.return_value = iter([
            ("messages", (AIMessageChunk(content="内部改写"), {"langgraph_node": "rewrite_query"})),
            ("messages", (AIMessageChunk(content="历史回答"), {"langgraph_node": "answer_from_history"})),
            ("messages", (AIMessageChunk(content="总结回答"), {"langgraph_node": "summarize_history"})),
            ("messages", (AIMessageChunk(content="知识库回答"), {"langgraph_node": "generate_answer"})),
            ("updates", {"finalize": {"evidence_level": "high", "outcome_category": "success"}}),
        ])
        body = ChatRequest(question="测试", web_search_enabled=False, search_strategy="balanced")

        events = list(ChatStreamService(body, kb=object(), authorized_workspace_id=body.workspace_id).run())
        token_texts = [
            json.loads(event["data"])["text"]
            for event in events
            if event["event"] == "token"
        ]

        self.assertEqual(token_texts, ["历史回答", "总结回答", "知识库回答"])
        self.assertNotIn("内部改写", token_texts)

    @patch.object(ChatStreamService, "_persist", return_value=("conv-1", 2))
    @patch("src.graph.quality_nodes.check_quality", side_effect=_accept_answer)
    @patch("src.graph.generation_nodes.generate_answer", side_effect=_generate_answer_from_sources)
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
        service = ChatStreamService(
            body,
            kb=WorkspaceScopedGraphKB(),
            authorized_workspace_id=body.workspace_id,
        )

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

    @patch("src.api.chat_stream_service.record_query_metrics")
    @patch.object(ChatStreamService, "_persist", return_value=("conv-1", 2))
    @patch("src.api.chat_stream_service.settings")
    @patch("src.api.chat_stream_service.run_query")
    def test_e2e_fake_chat_uses_imported_workspace_chunk_without_graph(
        self,
        mock_run_query,
        mock_settings,
        _mock_persist,
        _mock_record_query_metrics,
    ):
        mock_settings.e2e_fake_ai = True
        body = ChatRequest(
            question="团队问答是什么？",
            web_search_enabled=False,
            search_strategy="balanced",
            workspace_id="ws-e2e",
        )

        events = list(ChatStreamService(
            body,
            kb=E2EFakeChatKB(),
            authorized_workspace_id=body.workspace_id,
        ).run())
        done_payload = json.loads(next(event["data"] for event in events if event["event"] == "done"))
        sources_payload = json.loads(next(event["data"] for event in events if event["event"] == "sources"))

        mock_run_query.assert_not_called()
        self.assertIn("KnowBase 支持团队问答", done_payload["answer"])
        self.assertEqual(done_payload["sources"][0]["source"], "e2e-note.md")
        self.assertEqual(sources_payload["sources"][0]["chunk_id"], "ws-e2e::e2e-note.md:0:abc")


if __name__ == "__main__":
    unittest.main()
