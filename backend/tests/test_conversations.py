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

    def test_list_assistant_debug_pairs_preserves_preceding_user_question(self):
        conv = conversations.create_conversation("联网搜索测试", thread_id="thread-789")
        conversations.add_message(conv["id"], "user", "本地问题")
        conversations.add_message(conv["id"], "assistant", "本地回答", debug_info=json.dumps({"used_web_search": False}))
        conversations.add_message(conv["id"], "user", "需要联网吗")
        conversations.add_message(conv["id"], "assistant", "联网回答", debug_info=json.dumps({"used_web_search": True}))

        pairs = conversations.list_assistant_debug_pairs()

        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["thread_id"], "thread-789")
        self.assertEqual(pairs[0]["question"], "本地问题")
        self.assertFalse(pairs[0]["debug_info"]["used_web_search"])
        self.assertEqual(pairs[1]["question"], "需要联网吗")
        self.assertTrue(pairs[1]["debug_info"]["used_web_search"])


if __name__ == "__main__":
    unittest.main()
