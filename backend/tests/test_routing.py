import unittest
from unittest.mock import patch

from src.graph_nodes import (
    should_retry,
)
from src.graph_routing import (
    route_after_classifier,
    handle_clarification,
)


class ClarificationRoutingTests(unittest.TestCase):
    def test_route_after_classifier_routes_clarification(self):
        branch = route_after_classifier({"question_type": "clarification"})
        self.assertEqual(branch, "handle_clarification")

    def test_handle_clarification_returns_polite_prompt(self):
        state = {"question": "hello"}
        result = handle_clarification(state)
        self.assertIn("hello", result["answer"])
        self.assertTrue(result["quality_ok"])
        self.assertEqual(result["retry_strategy"], "none")

    def test_should_retry_rewrite_query_strategy(self):
        target = should_retry({
            "quality_ok": False,
            "retry_count": 0,
            "retry_strategy": "rewrite_query",
        })
        self.assertEqual(target, "rewrite_query")

    def test_should_retry_expand_retrieval_strategy(self):
        target = should_retry({
            "quality_ok": False,
            "retry_count": 0,
            "retry_strategy": "expand_retrieval",
        })
        self.assertEqual(target, "retrieve_docs")

    def test_should_retry_max_retries_exceeded(self):
        target = should_retry({
            "quality_ok": False,
            "retry_count": 100,
            "retry_strategy": "expand_retrieval",
        })
        self.assertEqual(target, "finalize")

    def test_should_retry_quality_ok(self):
        target = should_retry({
            "quality_ok": True,
            "retry_count": 0,
            "retry_strategy": "expand_retrieval",
        })
        self.assertEqual(target, "finalize")


if __name__ == "__main__":
    unittest.main()
