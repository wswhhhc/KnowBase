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

    # ── Workspace tests ──

    def test_default_workspace_created_on_init(self):
        """init_db creates the default workspace with id=''."""
        ws_list = conversations.list_workspaces()
        ids = [w["id"] for w in ws_list]
        self.assertIn("", ids)
        default = next(w for w in ws_list if w["id"] == "")
        self.assertEqual(default["name"], "默认工作区")

    def test_delete_workspace_reassigns_conversations_to_default(self):
        """Deleting a workspace moves its conversations to the default workspace."""
        ws = conversations.create_workspace("测试工作区")
        conv = conversations.create_conversation("测试对话", workspace_id=ws["id"])
        self.assertEqual(conv["workspace_id"], ws["id"])

        conversations.delete_workspace(ws["id"])

        # Conversation should now belong to default workspace
        reloaded = conversations.get_conversation(conv["id"])
        self.assertEqual(reloaded["workspace_id"], "")

    def test_list_workspaces_includes_default_first(self):
        """list_workspaces returns default workspace (id='') first."""
        conversations.create_workspace("项目 A")
        ws_list = conversations.list_workspaces()
        self.assertEqual(ws_list[0]["id"], "")

    def test_conversation_filtered_by_workspace(self):
        """list_conversations(workspace_id) only returns matching conversations."""
        ws1 = conversations.create_workspace("WS1")
        ws2 = conversations.create_workspace("WS2")
        conv1 = conversations.create_conversation("对话1", workspace_id=ws1["id"])
        conv2 = conversations.create_conversation("对话2", workspace_id=ws2["id"])

        ws1_convs = conversations.list_conversations(workspace_id=ws1["id"])
        ws2_convs = conversations.list_conversations(workspace_id=ws2["id"])
        self.assertEqual(len(ws1_convs), 1)
        self.assertEqual(ws1_convs[0]["id"], conv1["id"])
        self.assertEqual(len(ws2_convs), 1)
        self.assertEqual(ws2_convs[0]["id"], conv2["id"])

    def test_delete_default_workspace_allowed(self):
        """Deleting the default workspace is allowed (conversations stay with id='')."""
        conversations.delete_workspace("")
        # Re-init should re-create default workspace
        conversations.init_db()
        ws_list = conversations.list_workspaces()
        self.assertIn("", [w["id"] for w in ws_list])
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

        md = conversations.export_conversation(conv["id"], fmt="markdown")
        self.assertIn("导出测试", md)
        self.assertIn("你好", md)
        self.assertIn("你好！", md)
        self.assertIn("doc.md", md)

    def test_export_nonexistent_conversation_returns_empty(self):
        md = conversations.export_conversation("nonexistent", fmt="markdown")
        self.assertEqual(md, "")

    def test_export_json_returns_dict_for_existing(self):
        conv = conversations.create_conversation("JSON测试")
        conversations.add_message(conv["id"], "user", "对话内容")
        data = conversations.export_conversation(conv["id"], fmt="json", include_sources=True, include_debug=True)
        self.assertEqual(data["title"], "JSON测试")
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["role"], "用户")
        self.assertEqual(data["messages"][0]["content"], "对话内容")

    def test_export_json_returns_empty_dict_for_nonexistent(self):
        result = conversations.export_conversation("nonexistent", fmt="json")
        self.assertEqual(result, {})

    def test_export_markdown_include_debug_false_omits_debug(self):
        """Export with include_debug=False should not include debug info."""
        conv = conversations.create_conversation("调试测试")
        conv_id = conv["id"]
        conversations.add_message(conv_id, "user", "测试问题")
        debug_json = json.dumps({"evidence_level": "strong", "evidence_summary": "2个片段"})
        conversations.add_message(conv_id, "assistant", "测试回答", debug_info=debug_json)
        md = conversations.export_conversation(conv_id, fmt="markdown", include_debug=False)
        self.assertNotIn("证据等级", md)
        self.assertNotIn("evidence", md)

    def test_export_markdown_include_debug_true_shows_debug_summary(self):
        """Export with include_debug=True should include debug info summary."""
        conv = conversations.create_conversation("调试测试2")
        conv_id = conv["id"]
        conversations.add_message(conv_id, "user", "另一个问题")
        debug_json = json.dumps({
            "evidence_level": "strong",
            "evidence_summary": "2个本地片段",
            "outcome_category": "success",
            "rewritten_question": "改写后的问题",
            "retry_count": 1,
            "used_rerank": True,
            "used_web_search": True,
            "web_results_count": 3,
            "nodes": [{"name": "retrieve", "label": "检索", "elapsed_ms": 100}],
        })
        conversations.add_message(conv_id, "assistant", "完整回答", debug_info=debug_json)
        md = conversations.export_conversation(conv_id, fmt="markdown", include_debug=True)
        self.assertIn("证据等级", md)
        self.assertIn("改写后查询", md)
        self.assertIn("重试次数：1", md)
        self.assertIn("使用重排：是", md)
        self.assertIn("联网搜索：是（3 条）", md)
        self.assertIn("节点数：1", md)

    def test_export_json_sources_omitted_when_flag_false(self):
        """export_json with include_sources=False should not contain sources."""
        conv = conversations.create_conversation("来源测试")
        conversations.add_message(conv["id"], "assistant", "回答", sources=[{"source": "test.txt"}])
        data = conversations.export_conversation(conv["id"], fmt="json", include_sources=False)
        self.assertNotIn("sources", data["messages"][0])

    def test_export_json_debug_omitted_when_flag_false(self):
        """export_json with include_debug=False should not contain debug_info."""
        conv = conversations.create_conversation("调试测试3")
        conversations.add_message(conv["id"], "assistant", "回答", debug_info=json.dumps({"evidence_level": "weak"}))
        data = conversations.export_conversation(conv["id"], fmt="json", include_debug=False)
        self.assertNotIn("debug_info", data["messages"][0])

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
