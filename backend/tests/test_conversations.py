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
        updated = conversations.update_title(conv["id"], "新标题")
        stored = conversations.get_conversation(conv["id"])
        self.assertTrue(updated)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["title"], "新标题")

    def test_update_title_nonexistent_returns_false(self):
        self.assertFalse(conversations.update_title("missing-conv", "新标题"))

    def test_delete_conversation_cascades_messages(self):
        conv = conversations.create_conversation("删除测试")
        conversations.add_message(conv["id"], "user", "你好")
        conversations.add_message(conv["id"], "assistant", "你好！我是知识库助手。")
        messages_before = conversations.get_messages(conv["id"])
        self.assertEqual(len(messages_before), 2)

        deleted = conversations.delete_conversation(conv["id"])

        self.assertTrue(deleted)
        messages_after = conversations.get_messages(conv["id"])
        self.assertEqual(len(messages_after), 0)
        self.assertIsNone(conversations.get_conversation(conv["id"]))

    def test_delete_nonexistent_conversation(self):
        self.assertFalse(conversations.delete_conversation("nonexistent-id"))

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

        updated_ok = conversations.update_feedback(msg_id, "like")
        updated = conversations.get_messages(conv["id"])
        updated_assistant = [m for m in updated if m["role"] == "assistant"][0]
        self.assertTrue(updated_ok)
        self.assertEqual(updated_assistant["feedback"], "like")

    def test_update_feedback_dislike(self):
        conv = conversations.create_conversation("反馈测试2")
        conversations.add_message(conv["id"], "assistant", "回答")
        msgs = conversations.get_messages(conv["id"])
        msg_id = msgs[0]["id"]

        updated_ok = conversations.update_feedback(msg_id, "dislike")
        updated = conversations.get_messages(conv["id"])
        self.assertTrue(updated_ok)
        self.assertEqual(updated[0]["feedback"], "dislike")

    def test_update_feedback_nonexistent_returns_false(self):
        self.assertFalse(conversations.update_feedback(9999, "like"))

    def test_create_conversation_defaults_title(self):
        conv = conversations.create_conversation()
        self.assertEqual(conv["title"], "新对话")

    def test_get_conversation_by_thread_nonexistent(self):
        result = conversations.get_conversation_by_thread("no-such-thread")
        self.assertIsNone(result)

    def test_delete_conversations_batch(self):
        conv1 = conversations.create_conversation("批量1")
        conv2 = conversations.create_conversation("批量2")
        conv3 = conversations.create_conversation("保留")
        conversations.add_message(conv1["id"], "user", "a")
        conversations.add_message(conv2["id"], "assistant", "b")

        conversations.delete_conversations([conv1["id"], conv2["id"]])

        self.assertIsNone(conversations.get_conversation(conv1["id"]))
        self.assertIsNone(conversations.get_conversation(conv2["id"]))
        self.assertIsNotNone(conversations.get_conversation(conv3["id"]))
        self.assertEqual(conversations.get_messages(conv1["id"]), [])
        self.assertEqual(conversations.get_messages(conv2["id"]), [])

    def test_delete_conversations_empty_list_does_nothing(self):
        before = len(conversations.list_conversations())
        try:
            conversations.delete_conversations([])
        except Exception as e:
            self.fail(f"delete_conversations([]) raised {e}")
        self.assertEqual(len(conversations.list_conversations()), before)


if __name__ == "__main__":
    unittest.main()
