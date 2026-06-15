"""Tests for DebugInfo and NodeDebug Pydantic models."""
import unittest

from src.api.models import DebugInfo, NodeDebug


class DebugModelTests(unittest.TestCase):
    def test_node_debug_defaults(self):
        nd = NodeDebug(name="test", label="测试")
        self.assertEqual(nd.elapsed_ms, 0)
        self.assertEqual(nd.summary, "")

    def test_node_debug_with_values(self):
        nd = NodeDebug(name="retrieve_docs", label="混合检索", elapsed_ms=120, summary="30 候选")
        self.assertEqual(nd.name, "retrieve_docs")
        self.assertEqual(nd.label, "混合检索")
        self.assertEqual(nd.elapsed_ms, 120)

    def test_debug_info_roundtrip(self):
        info = DebugInfo(
            nodes=[NodeDebug(name="a", label="A", elapsed_ms=10, summary="ok")],
            rewritten_question="test query",
            used_rerank=True,
            quality_passed=False,
        )
        d = info.model_dump()
        restored = DebugInfo.model_validate(d)
        self.assertEqual(len(restored.nodes), 1)
        self.assertEqual(restored.rewritten_question, "test query")
        self.assertTrue(restored.used_rerank)
        self.assertFalse(restored.quality_passed)

    def test_debug_info_defaults(self):
        info = DebugInfo()
        self.assertEqual(len(info.nodes), 0)
        self.assertEqual(info.rewritten_question, "")
        self.assertTrue(info.quality_passed)
        self.assertEqual(info.retry_count, 0)
        self.assertFalse(info.used_web_search)

    def test_multiple_nodes_in_order(self):
        info = DebugInfo(
            nodes=[
                NodeDebug(name="route_question", label="问题路由", elapsed_ms=12, summary="→ knowledge_base"),
                NodeDebug(name="retrieve_docs", label="混合检索", elapsed_ms=340, summary="30 候选"),
            ]
        )
        self.assertEqual(len(info.nodes), 2)
        self.assertEqual(info.nodes[0].name, "route_question")
        self.assertEqual(info.nodes[1].elapsed_ms, 340)


if __name__ == "__main__":
    unittest.main()
