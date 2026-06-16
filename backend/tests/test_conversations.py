"""Extended tests for src.conversations — CRUD, export, feedback."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src import conversations


class ConversationEdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "conversations.db"
        self.original_path = conversations._DB_PATH
        conversations._DB_PATH = self.db_path
        conversations.init_db()

    def tearDown(self):
        conversations._DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_update_title_works(self):
        conv = conversations.create_conversation("旧标题")
        conversations.update_title(conv["id"], "新标题")
        stored = conversations.get_conversation(conv["id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["title"], "新标题")

    def test_delete_conversation_cascades_messages(self):
        conv = conversations.create_conversation("删除测试")
        conversations.add_message(conv["id"], "user", "你好")
        conversations.add_message(conv["id"], "assistant", "你好！我是知识库助手。")
        messages_before = conversations.get_messages(conv["id"])
        self.assertEqual(len(messages_before), 2)

        conversations.delete_conversation(conv["id"])

        messages_after = conversations.get_messages(conv["id"])
        self.assertEqual(len(messages_after), 0)
        self.assertIsNone(conversations.get_conversation(conv["id"]))

    def test_delete_nonexistent_conversation(self):
        """Deleting a non-existent conversation should not raise."""
        try:
            conversations.delete_conversation("nonexistent-id")
        except Exception as e:
            self.fail(f"delete_conversation raised {e}")

    def test_get_messages_empty_returns_empty_list(self):
        conv = conversations.create_conversation("空消息测试")
        messages = conversations.get_messages(conv["id"])
        self.assertEqual(messages, [])

    def test_get_messages_returns_in_order(self):
        conv = conversations.create_conversation("顺序测试")
        conversations.add_message(conv["id"], "user", "第一个")
        conversations.add_message(conv["id"], "assistant", "第二个")
        conversations.add_message(conv["id"], "user", "第三个")

        messages = conversations.get_messages(conv["id"])
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["content"], "第一个")
        self.assertEqual(messages[1]["content"], "第二个")
        self.assertEqual(messages[2]["content"], "第三个")

    def test_get_conversation_returns_none_for_nonexistent(self):
        result = conversations.get_conversation("does-not-exist")
        self.assertIsNone(result)

    def test_list_conversations_empty_returns_empty_list(self):
        result = conversations.list_conversations()
        self.assertEqual(result, [])

    def test_export_conversation_returns_markdown(self):
        conv = conversations.create_conversation("导出测试")
        conversations.add_message(conv["id"], "user", "你好")
        conversations.add_message(
            conv["id"],
            "assistant",
            "你好！",
            sources=[{"source": "doc.md", "index": 1}],
            quality_reason="ok",
        )

        md = conversations.export_conversation(conv["id"])
        self.assertIn("导出测试", md)
        self.assertIn("你好", md)
        self.assertIn("你好！", md)
        self.assertIn("doc.md", md)
        self.assertIn("ok", md)

    def test_export_nonexistent_conversation_returns_empty(self):
        md = conversations.export_conversation("nonexistent")
        self.assertEqual(md, "")

    def test_update_feedback_works(self):
        conv = conversations.create_conversation("反馈测试")
        conversations.add_message(conv["id"], "user", "问题")
        conversations.add_message(conv["id"], "assistant", "答案")

        messages = conversations.get_messages(conv["id"])
        assistant_msg = [m for m in messages if m["role"] == "assistant"][0]
        msg_id = assistant_msg["id"]

        conversations.update_feedback(msg_id, "like")
        updated = conversations.get_messages(conv["id"])
        updated_assistant = [m for m in updated if m["role"] == "assistant"][0]
        self.assertEqual(updated_assistant["feedback"], "like")

    def test_update_feedback_dislike(self):
        conv = conversations.create_conversation("反馈测试2")
        conversations.add_message(conv["id"], "assistant", "回答")
        msgs = conversations.get_messages(conv["id"])
        msg_id = msgs[0]["id"]

        conversations.update_feedback(msg_id, "dislike")
        updated = conversations.get_messages(conv["id"])
        self.assertEqual(updated[0]["feedback"], "dislike")

    def test_create_conversation_defaults_title(self):
        conv = conversations.create_conversation()
        self.assertEqual(conv["title"], "新对话")

    def test_get_conversation_by_thread_nonexistent(self):
        result = conversations.get_conversation_by_thread("no-such-thread")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
