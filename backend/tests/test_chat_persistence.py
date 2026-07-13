"""Tests for persisted chat debug payload metadata."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.api.chat_persistence import (
    ConversationWorkspaceMismatchError,
    build_debug_payload,
    persist_conversation_turn,
)
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

    @patch("src.api.chat_persistence.conversation_store.persist_conversation_turn")
    @patch("src.api.chat_persistence.conversation_store.get_conversation_by_thread")
    def test_persist_rejects_thread_bound_to_another_workspace(
        self,
        mock_get_conversation_by_thread,
        mock_persist_conversation_turn,
    ):
        mock_get_conversation_by_thread.return_value = {
            "id": "conv-other",
            "thread_id": "thread-shared",
            "workspace_id": "ws-other",
        }

        with self.assertRaises(ConversationWorkspaceMismatchError):
            persist_conversation_turn(
                question="不能跨工作区写入",
                thread_id="thread-shared",
                workspace_id="ws-requested",
                answer="拒绝写入",
                final_sources=[],
                final_quality="",
                debug_payload="{}",
                pinned_chunk_ids=[],
                excluded_chunk_ids=[],
            )

        mock_persist_conversation_turn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
