import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src import conversations


class ConversationStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "conversations.db"
        self.original_path = conversations._DB_PATH
        conversations._DB_PATH = self.db_path
        conversations.init_db()

    def tearDown(self):
        conversations._DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_create_conversation_uses_provided_thread_id_and_title(self):
        conv = conversations.create_conversation("周六是否上班", thread_id="thread-123")

        self.assertEqual(conv["title"], "周六是否上班")
        self.assertEqual(conv["thread_id"], "thread-123")

        stored = conversations.get_conversation_by_thread("thread-123")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["title"], "周六是否上班")
        self.assertEqual(stored["thread_id"], "thread-123")

    def test_add_message_updates_existing_conversation_found_by_thread(self):
        conv = conversations.create_conversation("LangGraph 会话持久化", thread_id="thread-456")
        conversations.add_message(conv["id"], "user", "LangGraph 支持 checkpoint 吗")
        conversations.add_message(conv["id"], "assistant", "支持", sources=[{"source": "doc.md"}], quality_reason="ok")

        messages = conversations.get_messages(conv["id"])
        self.assertEqual([msg["role"] for msg in messages], ["user", "assistant"])
        self.assertEqual(messages[1]["sources"], [{"source": "doc.md"}])

        row = conversations.get_conversation_by_thread("thread-456")
        self.assertEqual(row["id"], conv["id"])


if __name__ == "__main__":
    unittest.main()
