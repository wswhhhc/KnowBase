import unittest
from unittest.mock import patch
from uuid import uuid4

from langchain_core.documents import Document

from src.graph import (
    detect_question_type,
    parse_quality_decision,
    parse_rerank_decision,
    run_query,
    route_after_classifier,
    route_after_retrieval,
)
from src.knowledge_base import RetrievalResult


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, _prompt):
        if self.responses:
            return FakeResponse(self.responses.pop(0))
        return FakeResponse("fake answer")


class EmptyKnowledgeBase:
    def hybrid_search(self, *_args, **_kwargs):
        return []


class OneDocKnowledgeBase:
    def __init__(self):
        self.calls = 0

    def hybrid_search(self, *_args, **_kwargs):
        self.calls += 1
        doc = Document(
            page_content="LangGraph 支持 checkpoint 持久化会话状态。",
            metadata={"source": "langgraph.txt", "chunk_id": "langgraph.txt:0:abc"},
        )
        return [RetrievalResult(chunk_id="langgraph.txt:0:abc", document=doc, score=0.5)]


class GraphRoutingTests(unittest.TestCase):
    def test_detect_question_type_routes_history_memory_questions(self):
        history = [("一周放假几天", "两天。")]
        question_type = detect_question_type("你知道上一次我问了你什么吗", history)
        self.assertEqual(question_type, "chat_memory")

    def test_detect_question_type_routes_just_now_phrasing_to_memory(self):
        history = [("中午几点下班", "12:30。"), ("晚上呢", "18:00。")]
        question_type = detect_question_type("我刚刚问了什么", history)
        self.assertEqual(question_type, "chat_memory")

    def test_detect_question_type_routes_summary_questions(self):
        history = [("一周放假几天", "两天。")]
        question_type = detect_question_type("帮我总结一下刚才的对话", history)
        self.assertEqual(question_type, "conversation_summary")

    def test_detect_question_type_defaults_to_knowledge_base(self):
        history = [("一周放假几天", "两天。")]
        question_type = detect_question_type("试用期年假怎么算", history)
        self.assertEqual(question_type, "knowledge_base")

    def test_route_after_classifier_sends_memory_questions_to_memory_node(self):
        branch = route_after_classifier({"question_type": "chat_memory"})
        self.assertEqual(branch, "answer_from_history")

    def test_route_after_retrieval_handles_empty_results(self):
        branch = route_after_retrieval({"documents": []})
        self.assertEqual(branch, "handle_missing_context")

    def test_parse_rerank_decision_keeps_only_valid_doc_ids(self):
        decision = parse_rerank_decision(
            '{"selected_doc_ids":["a","missing"],"reason":"a is better"}',
            {"a", "b"},
        )

        self.assertEqual(decision.selected_doc_ids, ["a"])

    def test_parse_quality_decision_accepts_json(self):
        decision = parse_quality_decision(
            '{"quality_passed":false,"quality_reason":"证据不足","retry_strategy":"expand_retrieval"}'
        )

        self.assertFalse(decision.quality_passed)
        self.assertEqual(decision.retry_strategy, "expand_retrieval")

    def test_run_query_handles_missing_context_without_llm(self):
        result = run_query(
            question="不存在的问题",
            thread_id=str(uuid4()),
            knowledge_base=EmptyKnowledgeBase(),
        )

        self.assertIn("没有找到足够相关", result["answer"])
        self.assertEqual(result["sources"], [])

    def test_run_query_uses_thread_memory_for_followup(self):
        kb = EmptyKnowledgeBase()
        thread_id = str(uuid4())
        run_query(question="第一轮问什么", thread_id=thread_id, knowledge_base=kb)

        fake_llm = FakeLLM(["你上一轮问的是：第一轮问什么。"])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = run_query(
                question="我刚刚问了什么",
                thread_id=thread_id,
                knowledge_base=kb,
            )

        self.assertIn("第一轮问什么", result["answer"])

    def test_run_query_retries_with_expanded_retrieval_when_quality_fails(self):
        kb = OneDocKnowledgeBase()
        fake_llm = FakeLLM([
            '{"selected_doc_ids":["langgraph.txt:0:abc"],"reason":"relevant"}',
            "LangGraph 可以持久化会话状态。【来源：langgraph.txt】",
            '{"quality_passed":false,"quality_reason":"需要更多证据","retry_strategy":"expand_retrieval"}',
            '{"selected_doc_ids":["langgraph.txt:0:abc"],"reason":"relevant"}',
            "LangGraph 可以通过 checkpoint 持久化会话状态。【来源：langgraph.txt】",
            '{"quality_passed":true,"quality_reason":"PASS","retry_strategy":"none"}',
        ])

        with patch("src.graph._get_llm", return_value=fake_llm):
            result = run_query(
                question="LangGraph 如何记忆对话？",
                thread_id=str(uuid4()),
                knowledge_base=kb,
            )

        self.assertEqual(kb.calls, 2)
        self.assertTrue(result["quality_ok"])


if __name__ == "__main__":
    unittest.main()
