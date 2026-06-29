"""AST-based signature checks for chat stream persistence calls.

These tests verify that the calls within ChatStreamService._persist
pass the correct keyword arguments to record_query_metrics, ensuring
performance metadata (ttfb_ms, first_token_ms, etc.) are always forwarded.
"""

import ast
from pathlib import Path
import unittest


CHAT_SERVICE_PATH = Path(__file__).resolve().parents[1] / "src" / "api" / "chat_stream_service.py"


def _load_module():
    return ast.parse(CHAT_SERVICE_PATH.read_text(encoding="utf-8"))


class ChatMetricsSignatureTests(unittest.TestCase):
    def _find_record_query_metrics_call(self):
        """Walk AST looking for the record_query_metrics() call inside _persist."""
        module = _load_module()
        for node in module.body:
            if isinstance(node, ast.ClassDef) and node.name == "ChatStreamService":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "_persist":
                        for child in ast.walk(item):
                            if isinstance(child, ast.Call):
                                func = child.func
                                if isinstance(func, ast.Name) and func.id == "record_query_metrics":
                                    return {kw.arg for kw in child.keywords}
        return None

    def test_record_query_metrics_accepts_perf_kwargs(self):
        """_persist calls record_query_metrics with performance kwargs."""
        kw = self._find_record_query_metrics_call()
        self.assertIsNotNone(kw, "record_query_metrics call not found in _persist")
        self.assertIn("ttfb_ms", kw)
        self.assertIn("first_token_ms", kw)

    def test_persist_call_matches_record_signature(self):
        """_persist passes all required metrics kwargs to record_query_metrics."""
        kw = self._find_record_query_metrics_call()
        self.assertIsNotNone(kw, "record_query_metrics call not found in _persist")
        required = {"ttfb_ms", "first_token_ms", "token_count", "prompt_tokens", "completion_tokens"}
        self.assertTrue(
            required.issubset(kw),
            f"Missing kwargs: {required - kw}",
        )


if __name__ == "__main__":
    unittest.main()
