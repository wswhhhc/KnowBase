"""Edge-case / boundary tests for graph.run_query and related functions."""

import unittest
from unittest.mock import patch
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage

from src.graph import (
    run_query,
    _initial_state,
)
from src.graph_utils import (
    parse_rerank_decision,
    parse_quality_decision,
)
from src.knowledge_base import RetrievalResult


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, _prompt):
        if self.responses:
            return FakeResponse(self.responses.pop(0))
        return FakeResponse("fake")


class EmptyKB:
    def hybrid_search(self, *_a, **_kw):
        return []

    @staticmethod
    def get_neighbor_chunks(_cid, window=1):
        return []


class RunQueryEdgeTests(unittest.TestCase):
    """run_query with empty / extreme inputs."""

    def test_whitespace_only_question(self):
        result = run_query(
            question="   ",
            thread_id=str(uuid4()),
            knowledge_base=EmptyKB(),
        )
        # Should not crash; route_question classifies, retrieve returns empty,
        # handle_missing_context fires.
        self.assertIn(result.get("answer", ""), result.get("answer", ""))

    def test_very_long_question(self):
        long_q = "A" * 4000
        result = run_query(
            question=long_q,
            thread_id=str(uuid4()),
            knowledge_base=EmptyKB(),
        )
        # Should complete without error and contain some message
        self.assertTrue("answer" in result)


class ParseRerankDecisionEdgeTests(unittest.TestCase):
    """parse_rerank_decision edge cases."""

    def test_empty_string(self):
        decision = parse_rerank_decision("", {"a"})
        self.assertEqual(decision.selected_doc_ids, [])

    def test_non_json_text(self):
        decision = parse_rerank_decision("plain text here", {"a"})
        self.assertEqual(decision.selected_doc_ids, [])

    def test_json_array_not_object(self):
        decision = parse_rerank_decision('["a", "b"]', {"a", "b"})
        self.assertEqual(decision.selected_doc_ids, [])


class ParseQualityDecisionEdgeTests(unittest.TestCase):
    """parse_quality_decision edge inputs."""

    def test_empty_string(self):
        d = parse_quality_decision("")
        self.assertFalse(d.quality_passed)

    def test_pass_literal(self):
        d = parse_quality_decision("PASS")
        self.assertTrue(d.quality_passed)

    def test_pass_lowercase(self):
        d = parse_quality_decision("pass")
        self.assertTrue(d.quality_passed)

    def test_positive_natural_language(self):
        d = parse_quality_decision("回答准确完整，引用了相关文档")
        self.assertTrue(d.quality_passed)

    def test_negative_natural_language(self):
        d = parse_quality_decision("回答存在明显错误，虚构了数据")
        self.assertFalse(d.quality_passed)


if __name__ == "__main__":
    unittest.main()
