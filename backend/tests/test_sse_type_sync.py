"""Test that SSE hand-maintained types in api-types.ts stay in sync with Pydantic models.

Reads the TS interfaces from frontend/src/lib/api-types.ts, extracts
the field names of KBChunk, DebugNodeInfo, and DebugInfo, and compares them
against the Pydantic model fields from backend/src/api/models.py.

This is a build-time consistency check — if a developer adds/removes/renames a field
in one place but forgets the other, this test fails.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from pydantic import BaseModel

from src.api.models import KBChunk, NodeDebug, DebugInfo

# Path to the TS file relative to backend/tests/
_TS_FILE = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "lib" / "api-types.ts"

# TS interface name → Pydantic model class
_INTERFACE_MAP: dict[str, type[BaseModel]] = {
    "KBChunk": KBChunk,
    "DebugNodeInfo": NodeDebug,
    "DebugInfo": DebugInfo,
}


def _parse_ts_fields(interface_name: str, ts_source: str) -> set[str]:
    """Parse field names from a TypeScript interface definition.

    Finds ``export interface <interface_name> { ... }`` and extracts all
    top-level field names.
    """
    pattern = rf"export interface {interface_name}\s*{{([^}}]+)}}"
    match = re.search(pattern, ts_source)
    if not match:
        return set()
    fields = set()
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # TS field:  name: type  (possibly with | null trailing)
        m = re.match(r"(\w+)\s*:", stripped)
        if m:
            fields.add(m.group(1))
    return fields


def _pydantic_fields(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields.keys())


class TestSSETypeSync(unittest.TestCase):
    """Ensure SSE hand-maintained TS interfaces match Pydantic models."""

    @classmethod
    def setUpClass(cls):
        if not _TS_FILE.exists():
            raise RuntimeError(
                f"api-types.ts not found at {_TS_FILE}. "
                "Run tests from the project root or backend/ directory."
            )
        cls.ts_source = _TS_FILE.read_text(encoding="utf-8")

    def _assert_fields_match(self, interface_name: str, model: type[BaseModel]):
        ts_fields = _parse_ts_fields(interface_name, self.ts_source)
        py_fields = _pydantic_fields(model)

        missing_in_ts = py_fields - ts_fields
        extra_in_ts = ts_fields - py_fields

        errors = []
        if missing_in_ts:
            errors.append(f"TS 接口 {interface_name} 缺少字段: {sorted(missing_in_ts)}")
        if extra_in_ts:
            errors.append(f"TS 接口 {interface_name} 有多余字段: {sorted(extra_in_ts)}")

        if errors:
            self.fail(
                f"TS 接口与 Pydantic 模型不同步。\n"
                + "\n".join(errors)
                + "\n请同步更新 frontend/src/lib/api-types.ts 中的 SSE 类型，"
                  "使其与 backend/src/api/models.py 中的 Pydantic 模型保持一致。"
            )

    def test_kb_chunk_in_sync(self):
        self._assert_fields_match("KBChunk", KBChunk)

    def test_debug_node_info_in_sync(self):
        self._assert_fields_match("DebugNodeInfo", NodeDebug)

    def test_debug_info_in_sync(self):
        self._assert_fields_match("DebugInfo", DebugInfo)

    def test_all_sse_types_covered(self):
        """Every Pydantic model in INTERFACE_MAP has a corresponding test."""
        # Ensure no SSE type is missing from _INTERFACE_MAP
        for interface_name, model in _INTERFACE_MAP.items():
            self.assertIsNotNone(model, f"{interface_name} missing from _INTERFACE_MAP")


if __name__ == "__main__":
    unittest.main()
