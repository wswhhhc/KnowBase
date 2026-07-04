"""Extended conversation tests — list_assistant_debug_pairs, FK constraints, null sources."""

import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src import conversations
from src.persistence import database


class ConversationExtendedTests(unittest.TestCase):
    """Tests for list_assistant_debug_pairs and edge cases."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "conversations.db"
        self.original_path = conversations._DB_PATH
        conversations._DB_PATH = self.db_path
        conversations.init_db()

    def tearDown(self):
        conversations._DB_PATH = self.original_path
        database.clear_db_path_override()
        self.temp_dir.cleanup()

    # ── list_assistant_debug_pairs ──

    def test_debug_pairs_standard(self):
        """User + assistant with debug_info → parsed pair."""
        conv = conversations.create_conversation("test")
        conversations.add_message(conv["id"], "user", "年假几天")
        conversations.add_message(
            conv["id"], "assistant", "5天",
            debug_info=json.dumps({"used_rerank": True, "used_web_search": False}),
        )
        pairs = conversations.list_assistant_debug_pairs()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["question"], "年假几天")
        self.assertTrue(pairs[0]["debug_info"]["used_rerank"])

    def test_debug_pairs_orphan_assistant_skipped(self):
        """Assistant message without preceding user → skipped."""
        conv = conversations.create_conversation("test")
        conversations.add_message(conv["id"], "assistant", "hello")
        pairs = conversations.list_assistant_debug_pairs()
        self.assertEqual(pairs, [])

    def test_debug_pairs_malformed_json_returns_empty(self):
        """Malformed debug_info JSON → empty dict, no crash."""
        conv = conversations.create_conversation("test")
        conversations.add_message(conv["id"], "user", "hi")
        conn = conversations._get_conn()
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, debug_info, created_at) VALUES (?, ?, ?, ?, ?)",
            (conv["id"], "assistant", "hello", "{not json", "2026-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()
        pairs = conversations.list_assistant_debug_pairs()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["debug_info"], {})

    def test_debug_pairs_multiple_threads(self):
        """Messages from different thread_ids → paired per-thread."""
        conv1 = conversations.create_conversation("t1", thread_id="thread-a")
        conv2 = conversations.create_conversation("t2", thread_id="thread-b")
        conversations.add_message(conv1["id"], "user", "q1")
        conversations.add_message(conv1["id"], "assistant", "a1")
        conversations.add_message(conv2["id"], "user", "q2")
        conversations.add_message(conv2["id"], "assistant", "a2")
        pairs = conversations.list_assistant_debug_pairs()
        self.assertEqual(len(pairs), 2)

    # ── Edge cases ──

    def test_add_message_to_nonexistent_conversation(self):
        """Should not raise (FK constraint logged but not thrown)."""
        try:
            conversations.add_message("no-such-id", "user", "hello")
        except Exception as e:
            self.fail(f"add_message to nonexistent conv raised {e}")

    def test_get_messages_with_null_sources(self):
        """sources field stored as NULL in DB → returned as empty list."""
        conv = conversations.create_conversation("null sources")
        conn = conversations._get_conn()
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
            (conv["id"], "assistant", "hello", None, "2026-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()
        msgs = conversations.get_messages(conv["id"])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["sources"], [])

    def test_get_messages_with_null_debug_info(self):
        conv = conversations.create_conversation("null debug")
        conn = conversations._get_conn()
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, debug_info, created_at) VALUES (?, ?, ?, ?, ?)",
            (conv["id"], "assistant", "hello", None, "2026-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()
        msgs = conversations.get_messages(conv["id"])
        self.assertEqual(msgs[0]["debug_info"], {})

    def test_init_db_idempotent(self):
        """Calling init_db twice does not raise."""
        try:
            conversations.init_db()
            conversations.init_db()
        except Exception as e:
            self.fail(f"init_db raised on second call: {e}")

    def test_list_bookmarks_combines_workspace_and_search(self):
        ws_a = conversations.create_workspace("A")
        ws_b = conversations.create_workspace("B")
        conversations.create_bookmark(workspace_id=ws_a["id"], content="Alpha 片段", tags="alpha")
        conversations.create_bookmark(workspace_id=ws_b["id"], content="Alpha 片段", tags="alpha")

        results = conversations.list_bookmarks(workspace_id=ws_a["id"], search="Alpha")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["workspace_id"], ws_a["id"])

    def test_create_bookmark_deduplicates_workspace_chunk_pair(self):
        ws = conversations.create_workspace("Bookmarks")

        first = conversations.create_bookmark(
            workspace_id=ws["id"],
            chunk_id="doc.txt:0:abc",
            content="Alpha 片段",
            source="doc.txt",
        )
        second = conversations.create_bookmark(
            workspace_id=ws["id"],
            chunk_id="doc.txt:0:abc",
            content="Alpha 片段",
            source="doc.txt",
        )

        results = conversations.list_bookmarks(workspace_id=ws["id"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(results), 1)

    def test_delete_workspace_reassigns_bookmarks_to_default_workspace(self):
        ws = conversations.create_workspace("Workspace A")
        bookmark = conversations.create_bookmark(
            workspace_id=ws["id"],
            chunk_id="doc.txt:0:abc",
            content="Alpha 片段",
            source="doc.txt",
        )

        deleted = conversations.delete_workspace(ws["id"])

        self.assertTrue(deleted)
        reassigned = conversations.list_bookmarks(workspace_id="")
        self.assertEqual(len(reassigned), 1)
        self.assertEqual(reassigned[0]["id"], bookmark["id"])
        self.assertEqual(reassigned[0]["workspace_id"], "")


if __name__ == "__main__":
    unittest.main()
