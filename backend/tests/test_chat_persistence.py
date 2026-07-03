"""Tests for persisted chat debug payload metadata."""

from __future__ import annotations

import json
import unittest

from src.api.chat_persistence import build_debug_payload
from src.api.models import DebugInfo


class ChatPersistenceTests(unittest.TestCase):
    def test_build_debug_payload_includes_search_strategy(self):
        payload = build_debug_payload(
            DebugInfo(),
            evidence_level="moderate",
            evidence_summary="有部分证据",
            outcome_category="success",
            search_strategy="high_quality",
        )

        decoded = json.loads(payload)

        self.assertEqual(decoded["search_strategy"], "high_quality")
        self.assertEqual(decoded["evidence_level"], "moderate")
        self.assertEqual(decoded["outcome_category"], "success")


if __name__ == "__main__":
    unittest.main()
