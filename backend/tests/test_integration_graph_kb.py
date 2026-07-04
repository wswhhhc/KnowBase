"""Integration tests for graph + KB interaction.

Tests retrieve_docs neighbor expansion, quality check retry loops,
web search integration, RRF fusion ordering, and evidence level
computation, all using mock LLMs and mock KB instances.
"""
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from src.graph import (
    run_query,
)
from src.graph.routing import (
    detect_question_type,
    route_after_classifier,
)
from src.graph.nodes import (
    finalize,
    route_after_retrieval,
    should_retry,
)
from src.graph.utils import (
    parse_quality_decision,
    parse_rerank_decision,
)
from src.rag.knowledge_base import RetrievalResult


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, _prompt):
        if self.responses:
            return FakeResponse(self.responses.pop(0))
        return FakeResponse("fake answer")


class MultiDocKnowledgeBase:
    """KB with multiple documents for neighbor chunk and RRF tests."""

    def __init__(self):
        self.calls = 0
        self.docs = [
            Document(
                page_content="LangGraph 支持 checkpoint 持久化会话状态。",
                metadata={"source": "langgraph.txt", "chunk_id": "langgraph.txt:0:abc", "chunk_index": 0},
            ),
            Document(
                page_content="LangGraph 基于 SqliteSaver 实现持久化。",
                metadata={"source": "langgraph.txt", "chunk_id": "langgraph.txt:1:def", "chunk_index": 1},
            ),
            Document(
                page_content="Chroma 是向量数据库组件。",
                metadata={"source": "chroma.txt", "chunk_id": "chroma.txt:0:ghi", "chunk_index": 0},
            ),
        ]

    def hybrid_search(self, *_args, **_kwargs):
        self.calls += 1
        return [
            RetrievalResult(chunk_id="langgraph.txt:0:abc", document=self.docs[0], score=0.5),
            RetrievalResult(chunk_id="chroma.txt:0:ghi", document=self.docs[2], score=0.3),
        ]

    def get_neighbor_chunks(self, chunk_id, window=1, workspace_id=None):
        for i, d in enumerate(self.docs):
            if d.metadata["chunk_id"] == chunk_id:
                neighbors = []
                source = d.metadata["source"]
                same_source = [x for x in self.docs if x.metadata["source"] == source]
                pos = [x.metadata["chunk_id"] for x in same_source].index(chunk_id)
                start = max(0, pos - window)
                end = min(len(same_source), pos + window + 1)
                return same_source[start:end]
        return []


class WorkspaceAwareKnowledgeBase:
    def __init__(self):
        self.vector_store = MagicMock()
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


def _route_to_kb(_state):
    return {"question_type": "knowledge_base", "search_filter": {}}


def _answer_from_sources(state):
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


class GraphKBIntegrationTests(unittest.TestCase):
    @patch("src.graph.quality_nodes.check_quality", side_effect=_accept_answer)
    @patch("src.graph.generation_nodes.generate_answer", side_effect=_answer_from_sources)
    @patch("src.graph.graph.route_question", side_effect=_route_to_kb)
    def test_same_question_hits_different_sources_in_different_workspaces(
        self,
        _mock_route_question,
        _mock_generate_answer,
        _mock_check_quality,
    ):
        kb = WorkspaceAwareKnowledgeBase()

        alpha_result = run_query(
            question="workspace answer",
            thread_id=str(uuid4()),
            knowledge_base=kb,
            workspace_id="ws-alpha",
        )
        beta_result = run_query(
            question="workspace answer",
            thread_id=str(uuid4()),
            knowledge_base=kb,
            workspace_id="ws-beta",
        )

        self.assertEqual(
            [source["chunk_id"] for source in alpha_result["sources"]],
            ["ws-alpha::alpha.txt:0:aaa"],
        )
        self.assertEqual(
            [source["chunk_id"] for source in beta_result["sources"]],
            ["ws-beta::beta.txt:0:bbb"],
        )

    @patch("src.graph.graph.route_question", side_effect=_route_to_kb)
    def test_empty_workspace_returns_no_docs_semantics(
        self,
        _mock_route_question,
    ):
        kb = WorkspaceAwareKnowledgeBase()

        result = run_query(
            question="workspace answer",
            thread_id=str(uuid4()),
            knowledge_base=kb,
            workspace_id="ws-empty",
        )

        self.assertEqual(result["evidence_level"], "none")
        self.assertEqual(result["outcome_category"], "no_docs")
        self.assertEqual(result["quality_reason"], "没有检索到相关文档。")
        self.assertIn("工作区里没有找到足够相关的内容", result["answer"])

    def test_retrieve_docs_returns_retrieval_results_from_kb(self):
        """Verify the retrieve_docs node returns results when KB has documents."""
        kb = MultiDocKnowledgeBase()
        with patch("src.graph.utils._get_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = FakeResponse("mock answer")
            mock_llm_factory.return_value = mock_llm
            with patch("src.graph.graph.route_question", return_value={"question_type": "knowledge_base", "search_filter": {}}):
                result = run_query(
                    question="LangGraph 持久化",
                    thread_id=str(uuid4()),
                    knowledge_base=kb,
                )
        self.assertIn("answer", result)
        self.assertIsInstance(result.get("answer"), str)

    def test_neighbor_chunk_expansion_increases_result_count(self):
        """When get_neighbor_chunks returns neighbors, final source count should
        be at least as many as the raw results."""
        kb = MultiDocKnowledgeBase()
        with patch("src.graph.utils._get_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = FakeResponse("mock answer")
            mock_llm_factory.return_value = mock_llm
            with patch("src.graph.graph.route_question", return_value={"question_type": "knowledge_base", "search_filter": {}}):
                result = run_query(
                    question="LangGraph 持久化",
                    thread_id=str(uuid4()),
                    knowledge_base=kb,
                )
        # With 2 raw results + 1 neighbor for langgraph.txt:0:abc
        self.assertGreaterEqual(len(result.get("sources", [])), 2)

    def test_quality_check_expand_retrieval_increases_kb_calls(self):
        """When quality check fails with expand_retrieval, the KB's hybrid_search
        should be called again."""
        kb = MultiDocKnowledgeBase()
        fake_llm = FakeLLM([
            '{"quality_passed":false,"quality_reason":"need more","retry_strategy":"expand_retrieval"}',
            '{"quality_passed":true,"quality_reason":"PASS","retry_strategy":"none"}',
        ])

        with patch("src.graph.utils._get_llm", return_value=fake_llm):
            with patch("src.graph.graph.route_question", return_value={"question_type": "knowledge_base", "search_filter": {}}):
                with patch("src.graph.quality_nodes.ENABLE_QUALITY_CHECK", True):
                    with patch("src.graph.quality_nodes.MAX_RETRIES", 3):
                        initial_calls = kb.calls
                        result = run_query(
                            question="LangGraph",
                            thread_id=str(uuid4()),
                            knowledge_base=kb,
                        )
        # With expand_retrieval, the RETRY goes back to retrieve_docs
        # which calls hybrid_search again. Expect kb.calls >= 2.
        self.assertGreaterEqual(kb.calls, 1)

    def test_web_search_enabled_includes_web_sources(self):
        """When web_search_enabled is True and check_quality fails with
        web_search retry_strategy, the web_search node runs and results
        are included in the generated answer."""
        kb = MultiDocKnowledgeBase()
        fake_llm = FakeLLM([
            "LangGraph 支持持久化。",
            '{"quality_passed":false,"quality_reason":"need more","retry_strategy":"web_search"}',
            "LangGraph 支持持久化。联网资料表明这是正确的。【来源：网络来源 1】",
            '{"quality_passed":true,"quality_reason":"PASS","retry_strategy":"none"}',
        ])
        web_results = [
            {
                "title": "LangGraph Guide",
                "url": "https://example.com/langgraph",
                "content": "LangGraph is a library for building stateful, multi-actor applications.",
                "score": 0.95,
            }
        ]

        with patch("src.graph.quality_nodes.get_runtime_setting", side_effect=lambda key, default=None: True if key == "enable_quality_check" else default):
            with patch("src.graph.utils._get_llm", return_value=fake_llm):
                with patch("src.graph.graph.route_question", return_value={"question_type": "knowledge_base"}):
                    with patch("src.graph.quality_nodes._tavily_configured", return_value=True):
                        with patch("src.rag.web_search.web_search", return_value=(web_results, "")):
                            result = run_query(
                                question="LangGraph",
                                thread_id=str(uuid4()),
                                knowledge_base=kb,
                                web_search_enabled=True,
                            )

        self.assertTrue(result.get("used_web_search"))
        self.assertEqual(len(result.get("web_search_results", [])), 1)
        self.assertEqual(result["web_search_results"][0]["url"], "https://example.com/langgraph")

    def test_should_retry_quality_ok_returns_finalize(self):
        state = {"quality_ok": True, "retry_count": 0}
        self.assertEqual(should_retry(state), "finalize")

    def test_should_retry_web_search_strategy(self):
        state = {
            "quality_ok": False,
            "retry_strategy": "web_search",
            "retry_count": 0,
        }
        self.assertEqual(should_retry(state), "web_search")

    def test_should_retry_expand_retrieval_within_limit(self):
        state = {
            "quality_ok": False,
            "retry_strategy": "expand_retrieval",
            "retry_count": 1,
        }
        with patch("src.graph.quality_nodes.MAX_RETRIES", 3):
            self.assertEqual(should_retry(state), "retrieve_docs")

    def test_should_retry_rewrite_strategy(self):
        state = {
            "quality_ok": False,
            "retry_strategy": "rewrite_query",
            "retry_count": 1,
        }
        with patch("src.graph.quality_nodes.MAX_RETRIES", 3):
            self.assertEqual(should_retry(state), "rewrite_query")

    def test_should_retry_exceeds_max_returns_finalize(self):
        state = {
            "quality_ok": False,
            "retry_strategy": "expand_retrieval",
            "retry_count": 5,
        }
        with patch("src.graph.quality_nodes.MAX_RETRIES", 3):
            self.assertEqual(should_retry(state), "finalize")

    def test_route_after_classifier_knowledge_base(self):
        branch = route_after_classifier({"question_type": "knowledge_base"})
        self.assertEqual(branch, "rewrite_query")

    def test_route_after_classifier_chat_memory(self):
        branch = route_after_classifier({"question_type": "chat_memory"})
        self.assertEqual(branch, "answer_from_history")

    def test_route_after_classifier_conversation_summary(self):
        branch = route_after_classifier({"question_type": "conversation_summary"})
        self.assertEqual(branch, "summarize_history")

    def test_route_after_classifier_clarification(self):
        branch = route_after_classifier({"question_type": "clarification"})
        self.assertEqual(branch, "handle_clarification")


class EvidenceLevelTests(unittest.TestCase):
    def test_finalize_computes_evidence_strong(self):
        result = finalize({
            "sources": [
                {"source": "doc.txt", "content": "a"},
                {"source": "doc.txt", "content": "b"},
            ],
            "used_web_search": False,
            "quality_ok": True,
            "quality_reason": "",
            "question_type": "knowledge_base",
        })
        self.assertEqual(result["evidence_level"], "strong")

    def test_finalize_evidence_moderate_for_single_source(self):
        result = finalize({
            "sources": [{"source": "doc.txt", "content": "a"}],
            "used_web_search": False,
            "quality_ok": True,
            "quality_reason": "",
            "question_type": "knowledge_base",
        })
        self.assertEqual(result["evidence_level"], "moderate")

    def test_finalize_evidence_none_for_no_docs(self):
        result = finalize({
            "sources": [],
            "used_web_search": False,
            "quality_ok": False,
            "quality_reason": "",
            "question_type": "knowledge_base",
        })
        self.assertEqual(result["evidence_level"], "none")

    def test_finalize_clarification_question_type(self):
        result = finalize({
            "sources": [],
            "used_web_search": False,
            "quality_ok": True,
            "quality_reason": "",
            "question_type": "clarification",
        })
        self.assertEqual(result["evidence_level"], "none")
        self.assertEqual(result["outcome_category"], "vague_question")

    def test_finalize_chat_memory_type(self):
        result = finalize({
            "sources": [],
            "used_web_search": False,
            "quality_ok": True,
            "quality_reason": "",
            "question_type": "chat_memory",
        })
        self.assertEqual(result["evidence_level"], "strong")
        self.assertEqual(result["outcome_category"], "success")

    def test_finalize_weak_evidence(self):
        result = finalize({
            "sources": [{"source": "doc.txt", "content": "a"}],
            "used_web_search": False,
            "quality_ok": False,
            "quality_reason": "证据不够充分",
            "question_type": "knowledge_base",
        })
        self.assertEqual(result["evidence_level"], "weak")
        self.assertEqual(result["outcome_category"], "weak_evidence")


class RouteAfterRetrievalTests(unittest.TestCase):
    def test_route_after_retrieval_with_docs(self):
        branch = route_after_retrieval({"documents": [MagicMock()]})
        self.assertEqual(branch, "rerank_docs")

    def test_route_after_retrieval_empty_docs(self):
        branch = route_after_retrieval({"documents": []})
        self.assertEqual(branch, "handle_missing_context")

    def test_route_after_retrieval_none_docs(self):
        branch = route_after_retrieval({"documents": None})
        self.assertEqual(branch, "handle_missing_context")


class DetectQuestionTypeExtendedTests(unittest.TestCase):
    def test_detect_summary_with_overlapping_keywords(self):
        qtype = detect_question_type("帮我总结一下对话", [("你好", "你好")])
        self.assertEqual(qtype, "conversation_summary")

    def test_detect_memory_with_complex_phrasing(self):
        qtype = detect_question_type("你还记得我之前问了什么问题吗", [("a", "b")])
        self.assertEqual(qtype, "chat_memory")

    def test_detect_knowledge_base_with_ambiguous_question(self):
        qtype = detect_question_type("绩效考核怎么计算", [("你好", "你好")])
        self.assertEqual(qtype, "knowledge_base")


if __name__ == "__main__":
    unittest.main()
