import ast
from pathlib import Path
import unittest


CHAT_ROUTE_PATH = Path(__file__).resolve().parents[1] / "src" / "api" / "routes" / "chat.py"


def _load_module():
    return ast.parse(CHAT_ROUTE_PATH.read_text(encoding="utf-8"))


class ChatMetricsSignatureTests(unittest.TestCase):
    def test_record_query_metrics_accepts_perf_kwargs(self):
        module = _load_module()
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_record_query_metrics":
                kwonly = [arg.arg for arg in node.args.kwonlyargs]
                self.assertIn("ttfb_ms", kwonly)
                self.assertIn("first_token_ms", kwonly)
                return
        self.fail("Function _record_query_metrics not found")

    def test_persist_call_matches_record_signature(self):
        module = _load_module()
        signature = None
        call_kwargs = None

        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_record_query_metrics":
                signature = {arg.arg for arg in node.args.kwonlyargs}
            if isinstance(node, ast.FunctionDef) and node.name == "_persist_and_record":
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "_record_query_metrics":
                        call_kwargs = {kw.arg for kw in child.keywords}

        self.assertIsNotNone(signature)
        self.assertIsNotNone(call_kwargs)
        self.assertTrue(call_kwargs.issubset(signature))


if __name__ == "__main__":
    unittest.main()
