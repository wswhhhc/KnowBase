"""AST-based signature checks for chat stream persistence calls.

These tests verify that ``ChatStreamService`` keeps persistence encapsulated:
``_persist`` should read everything from instance state, be invoked without
arguments, and still forward performance metadata to ``record_query_metrics``.
"""

import ast
from pathlib import Path
import unittest


CHAT_SERVICE_PATH = Path(__file__).resolve().parents[1] / "src" / "api" / "chat_stream_service.py"


def _load_module():
    return ast.parse(CHAT_SERVICE_PATH.read_text(encoding="utf-8"))


class ChatMetricsSignatureTests(unittest.TestCase):
    def _find_method(self, class_name: str, method_name: str):
        module = _load_module()
        for node in module.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == method_name:
                        return item
        return None

    def _find_record_query_metrics_call(self):
        """Walk AST looking for the record_query_metrics() call inside _persist."""
        persist = self._find_method("ChatStreamService", "_persist")
        if persist is None:
            return None
        for child in ast.walk(persist):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name) and func.id == "record_query_metrics":
                    return {kw.arg for kw in child.keywords}
        return None

    def _find_persist_call(self):
        emit_completion = self._find_method("ChatStreamService", "_emit_completion")
        if emit_completion is None:
            return None
        for child in ast.walk(emit_completion):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id == "self" and func.attr == "_persist":
                        return child
        return None

    def test_persist_method_uses_only_self(self):
        """_persist should be a zero-arg instance method after the refactor."""
        persist = self._find_method("ChatStreamService", "_persist")
        self.assertIsNotNone(persist, "_persist method not found")
        arg_names = [arg.arg for arg in persist.args.args]
        self.assertEqual(arg_names, ["self"], f"_persist should only accept self, got {arg_names}")

    def test_emit_completion_calls_persist_without_arguments(self):
        """_emit_completion should persist from instance state instead of passing args through."""
        persist_call = self._find_persist_call()
        self.assertIsNotNone(persist_call, "self._persist() call not found in _emit_completion")
        self.assertEqual(len(persist_call.args), 0, "_persist() should not receive positional arguments")
        self.assertEqual(len(persist_call.keywords), 0, "_persist() should not receive keyword arguments")

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
