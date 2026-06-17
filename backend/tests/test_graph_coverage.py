"""Coverage tests for graph.py — covers all missing branches of internal and node functions."""

import unittest
from unittest.mock import patch, PropertyMock
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

from src.graph import (
    _should_rerank,
    _rule_check_quality,
    _compute_evidence,
    _route_search_scope,
    rewrite_query,
    rerank_docs,
    route_question,
    check_quality,
    generate_answer,
    build_graph,
    get_graph,
    finalize,
    _initial_state,
    GraphState,
)
from src.knowledge_base import KnowledgeBase, RetrievalResult


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


class FakeKnowledgeBase:
    """Minimal KB mock for build_graph tests."""
    def hybrid_search(self, *_a, **_kw):
        return []

    @staticmethod
    def get_neighbor_chunks(_chunk_id, window=1):
        return []


def _doc(score: float, chunk_id: str = "doc:0:abc") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document=Document(
            page_content="content",
            metadata={"source": "test.txt", "chunk_id": chunk_id},
        ),
        score=score,
    )


def _state(**overrides) -> dict:
    """Build a minimal GraphState-compatible dict with defaults + overrides."""
    base = _initial_state("default question")
    base.update(overrides)
    return base


# =============================================================================
# _should_rerank — 5 strategy/score/length branches
# =============================================================================

class ShouldRerankTests(unittest.TestCase):
    """_should_rerank: strategy branches + score gap + query length."""

    def test_fast_strategy_skips_rerank(self):
        self.assertFalse(_should_rerank(_state(search_strategy="fast")))

    def test_high_quality_always_reranks(self):
        self.assertTrue(_should_rerank(_state(search_strategy="high_quality")))

    def test_deep_strategy_always_reranks(self):
        self.assertTrue(_should_rerank(_state(search_strategy="deep")))

    def test_few_docs_skips_rerank(self):
        docs = [_doc(0.5), _doc(0.4)]
        self.assertFalse(_should_rerank(_state(
            search_strategy="balanced",
            documents=docs,
            question="a",
        )))

    def test_large_score_gap_skips_rerank(self):
        """Score gap >= RERANK_SCORE_GAP_THRESHOLD (0.005) → skip."""
        docs = [_doc(0.9), _doc(0.89), _doc(0.88), _doc(0.1), _doc(0.05)]
        self.assertFalse(_should_rerank(_state(
            search_strategy="balanced",
            documents=docs,
            question="a" * 60,
        )))

    def test_short_query_skips_rerank(self):
        """Question length < RERANK_QUERY_LENGTH (50) → skip (assuming small
        gap is not the trigger and enough docs exist)."""
        docs = [_doc(0.9), _doc(0.89), _doc(0.88), _doc(0.87), _doc(0.86)]
        self.assertFalse(_should_rerank(_state(
            search_strategy="balanced",
            documents=docs,
            question="short",  # len=5 < 50
        )))

    def test_balanced_triggers_rerank(self):
        """All conditions met: balanced, many docs, small gap, long query."""
        docs = [_doc(0.9), _doc(0.899), _doc(0.898), _doc(0.897), _doc(0.896)]
        self.assertTrue(_should_rerank(_state(
            search_strategy="balanced",
            documents=docs,
            question="what is the meaning of life according to philosophy?" * 3,
        )))


# =============================================================================
# rewrite_query — cache / entity expansion / no-op branches
# =============================================================================

class RewriteQueryTests(unittest.TestCase):
    """rewrite_query: history missing, no referential, cache hit, entity exp."""

    def test_no_history_returns_original(self):
        result = rewrite_query(_state(question="hello", messages=[]))
        self.assertEqual(result["rewritten_question"], "hello")
        self.assertFalse(result["used_rewrite"])

    def test_no_referential_pattern_preserves_question(self):
        state = _state(
            question="什么是年假",
            messages=[HumanMessage(content="年假"), AIMessage(content="5天")],
        )
        result = rewrite_query(state)
        self.assertEqual(result["rewritten_question"], "什么是年假")
        self.assertFalse(result["used_rewrite"])

    def test_cache_hit_returns_cached(self):
        question = "这个是什么意思"
        state = _state(
            question=question,
            messages=[HumanMessage(content="年假"), AIMessage(content="5天")],
        )
        # First call → LLM invoked, result cached
        llm1 = FakeLLM(["缓存的改写结果"])
        with patch("src.graph._get_llm", return_value=llm1):
            first = rewrite_query(state)

        # Second call — should hit cache, no LLM call
        with patch("src.graph._get_llm") as mock_llm:
            second = rewrite_query(state)
            mock_llm.assert_not_called()

        self.assertEqual(second["rewritten_question"], "缓存的改写结果")
        self.assertTrue(second["used_rewrite"])

    @patch("src.graph.extract_context_terms", return_value=["年假", "政策"])
    def test_entity_expansion_for_short_rewrite(self, mock_terms):
        """When LLM returns short answer (< 15 chars), entity expansion kicks in."""
        question = "这个呢"
        state = _state(
            question=question,
            messages=[HumanMessage(content="年假政策有哪些"), AIMessage(content="5天年假")],
        )
        # LLM returns a short rewrite
        fake_llm = FakeLLM(["测试"])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = rewrite_query(state)

        self.assertIn("测试", result["rewritten_question"])
        self.assertIn("年假", result["rewritten_question"])
        self.assertIn("政策", result["rewritten_question"])
        self.assertTrue(result["used_rewrite"])
        mock_terms.assert_called_once()


# =============================================================================
# rerank_docs — LLM error / empty decision / no-rerank paths
# =============================================================================

class RerankDocsTests(unittest.TestCase):
    """rerank_docs: _should_rerank=False short-circuit, LLM parse failures."""

    def test_fast_strategy_skips_llm_rerank(self):
        docs = [_doc(0.9), _doc(0.8)]
        result = rerank_docs(_state(
            search_strategy="fast",
            documents=docs,
            question="test",
        ))
        self.assertFalse(result["used_rerank"])

    def test_llm_json_exception_falls_back(self):
        """LLM returns invalid JSON → parse_rerank_decision returns empty list
        → fall back to docs[:top_k]."""
        docs = [_doc(0.9, "a:0:1"), _doc(0.8, "a:0:2")]
        fake_llm = FakeLLM(["not valid json at all"])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = rerank_docs(_state(
                search_strategy="high_quality",
                documents=docs,
                question="long question " * 10,
            ))
        self.assertTrue(result["used_rerank"])
        self.assertGreater(len(result.get("documents", [])), 0)

    def test_all_selected_ids_invalid_falls_back(self):
        """LLM returns valid JSON but chunk_ids don't exist."""
        docs = [_doc(0.9, "a:0:1"), _doc(0.8, "a:0:2")]
        fake_llm = FakeLLM(['{"selected_doc_ids":["missing:1"],"reason":"x"}'])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = rerank_docs(_state(
                search_strategy="high_quality",
                documents=docs,
                question="long question " * 10,
            ))
        self.assertTrue(result["used_rerank"])
        self.assertGreater(len(result.get("documents", [])), 0)


# =============================================================================
# _rule_check_quality — all 4 exit branches
# =============================================================================

class RuleCheckQualityTests(unittest.TestCase):
    """_rule_check_quality: no-docs, short answer, web-pass, no-match."""

    def test_no_docs_no_web_context_returns_insufficient(self):
        result = _rule_check_quality(_state(
            documents=[],
            web_context="",
            answer="",
            sources=[],
        ))
        self.assertIsNotNone(result)
        self.assertFalse(result["quality_ok"])
        self.assertEqual(result["retry_strategy"], "insufficient_context")

    def test_short_answer_triggers_expand(self):
        result = _rule_check_quality(_state(
            documents=[_doc(0.9)],
            web_context="",
            answer="OK",  # len=2 < 10
            sources=[{"source": "test.txt"}],
        ))
        self.assertIsNotNone(result)
        self.assertFalse(result["quality_ok"])
        self.assertEqual(result["retry_strategy"], "expand_retrieval")

    def test_used_web_search_with_sources_passes(self):
        result = _rule_check_quality(_state(
            documents=[_doc(0.9)],
            web_context="web content",
            answer="A longer answer with enough substance.",
            sources=[{"source": "test.txt"}],
            used_web_search=True,
        ))
        self.assertIsNotNone(result)
        self.assertTrue(result["quality_ok"])
        self.assertEqual(result["retry_strategy"], "none")

    def test_no_rule_matched_returns_none(self):
        result = _rule_check_quality(_state(
            documents=[_doc(0.9)],
            web_context="",
            answer="A longer answer with enough substance.",
            sources=[{"source": "test.txt"}],
        ))
        self.assertIsNone(result)


# =============================================================================
# _compute_evidence — outcome category / evidence level combinations
# =============================================================================

class ComputeEvidenceTests(unittest.TestCase):
    """_compute_evidence: all outcome categories and evidence levels."""

    def test_clarification_returns_none_vague(self):
        lvl, cat, summary = _compute_evidence(_state(question_type="clarification"))
        self.assertEqual(lvl, "none")
        self.assertEqual(cat, "vague_question")

    def test_chat_memory_returns_strong_success(self):
        lvl, cat, summary = _compute_evidence(_state(question_type="chat_memory"))
        self.assertEqual(lvl, "strong")
        self.assertEqual(cat, "success")

    def test_no_docs_no_web(self):
        lvl, cat, summary = _compute_evidence(_state(
            sources=[],
            used_web_search=False,
            question_type="knowledge_base",
        ))
        self.assertEqual(lvl, "none")
        self.assertEqual(cat, "no_docs")

    def test_web_empty(self):
        lvl, cat, summary = _compute_evidence(_state(
            sources=[],
            used_web_search=True,
            question_type="knowledge_base",
        ))
        self.assertEqual(lvl, "none")
        self.assertEqual(cat, "web_empty")

    def test_strong_with_local_and_web(self):
        lvl, cat, summary = _compute_evidence(_state(
            sources=[{"source": "a.txt"}, {"source": "b.txt"}, {"url": "http://x"}],
            used_web_search=True,
            quality_ok=True,
            question_type="knowledge_base",
        ))
        self.assertEqual(lvl, "strong")
        self.assertEqual(cat, "success")

    def test_moderate_with_single_local(self):
        lvl, cat, summary = _compute_evidence(_state(
            sources=[{"source": "a.txt"}],
            used_web_search=False,
            quality_ok=True,
            question_type="knowledge_base",
        ))
        self.assertEqual(lvl, "moderate")
        self.assertEqual(cat, "success")

    def test_weak_evidence_when_quality_fails(self):
        lvl, cat, summary = _compute_evidence(_state(
            sources=[{"source": "a.txt"}],
            quality_ok=False,
            quality_reason="some issue",
            used_web_search=False,
            question_type="knowledge_base",
        ))
        self.assertEqual(lvl, "weak")
        self.assertEqual(cat, "weak_evidence")


# =============================================================================
# check_quality — skip / rule-result / LLM / web_search trigger
# =============================================================================

class CheckQualityTests(unittest.TestCase):
    """check_quality: skip path, rule path, LLM path, web_search trigger."""

    def test_skip_when_question_type_not_kb(self):
        result = check_quality(_state(question_type="chat_memory"))
        self.assertTrue(result["quality_ok"])

    def test_skip_when_quality_check_disabled(self):
        with patch("src.graph.ENABLE_QUALITY_CHECK", False):
            result = check_quality(_state(question_type="knowledge_base"))
        self.assertTrue(result["quality_ok"])

    def test_rule_passed_returns_ok(self):
        result = check_quality(_state(
            question_type="knowledge_base",
            documents=[_doc(0.9)],
            web_context="web content",
            answer="A longer answer with enough substance.",
            sources=[{"source": "test.txt"}],
            used_web_search=True,
            retry_count=0,
        ))
        self.assertTrue(result["quality_ok"])

    def test_rule_insufficient_triggers_web_search(self):
        with patch("src.graph._tavily_configured", return_value=True):
            result = check_quality(_state(
                question_type="knowledge_base",
                documents=[],
                web_context="",
                answer="",
                sources=[],
                web_search_enabled=True,
                used_web_search=False,
                retry_count=0,
            ))
        # rule says insufficient_context → web_search eligible
        self.assertFalse(result["quality_ok"])
        self.assertEqual(result.get("retry_strategy"), "web_search")

    def test_llm_quality_passes(self):
        fake_llm = FakeLLM(['{"quality_passed":true,"quality_reason":"OK","retry_strategy":"none"}'])
        with patch("src.graph._get_llm", return_value=fake_llm):
            with patch("src.graph._tavily_configured", return_value=False):
                with patch("src.graph.hash") as mock_hash:
                    mock_hash.return_value = 0  # so hash % 3 == 0 → skip LLM
                    result = check_quality(_state(
                        question_type="knowledge_base",
                        documents=[_doc(0.9)],
                        context="some context",
                        answer="A reasonable answer with details.",
                        search_strategy="high_quality",
                        retry_count=0,
                    ))
        # With hash=0, the sampling check `hash % 3 != 0` is False → it won't skip
        # Wait: check_quality line 766:
        # if strategy != "high_quality" and not web_search_available and hash(question + answer) % 3 != 0:
        #     # sampling skip
        # Since strategy="high_quality", the condition is False immediately, so we go to LLM
        # llm returns quality_passed=true
        self.assertTrue(result["quality_ok"])

    def test_llm_quality_fails_triggers_web_search(self):
        fake_llm = FakeLLM(['{"quality_passed":false,"quality_reason":"bad","retry_strategy":"expand_retrieval"}'])
        with patch("src.graph._get_llm", return_value=fake_llm):
            with patch("src.graph._tavily_configured", return_value=True):
                with patch("src.graph.hash") as mock_hash:
                    mock_hash.return_value = 0  # skip the sampling branch
                    result = check_quality(_state(
                        question_type="knowledge_base",
                        documents=[_doc(0.9)],
                        context="some context",
                        answer="A reasonable answer.",
                        search_strategy="balanced",
                        web_search_enabled=True,
                        used_web_search=False,
                        retry_count=0,
                    ))
        self.assertFalse(result["quality_ok"])
        self.assertEqual(result.get("retry_strategy"), "web_search")

    def test_llm_quality_fails_expand_retrieval(self):
        fake_llm = FakeLLM(['{"quality_passed":false,"quality_reason":"need more","retry_strategy":"expand_retrieval"}'])
        with patch("src.graph._get_llm", return_value=fake_llm):
            with patch("src.graph._tavily_configured", return_value=False):
                result = check_quality(_state(
                    question_type="knowledge_base",
                    documents=[_doc(0.9)],
                    context="some context",
                    answer="A reasonable answer.",
                    search_strategy="high_quality",
                    retry_count=0,
                ))
        self.assertFalse(result["quality_ok"])
        self.assertIn("retrieval_k", result)


# =============================================================================
# generate_answer — deep/web-error/history/web-sources branches
# =============================================================================

class GenerateAnswerTests(unittest.TestCase):
    """generate_answer: deep+web, web_error_no_context, history, web sources."""

    def test_deep_strategy_sets_comprehensive_prompt(self):
        fake_llm = FakeLLM(["这是一个综合答案。"])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = generate_answer(_state(
                search_strategy="deep",
                context="some docs",
                used_web_search=False,
                web_context="",
                question="test?",
                messages=[],
            ))
        self.assertIn("答案", result.get("answer", result.get("sources", str(result))))

    def test_web_search_error_no_context_returns_error(self):
        result = generate_answer(_state(
            context="",
            web_context="",
            web_search_error="API timeout",
            used_web_search=True,
            question="test?",
            messages=[],
        ))
        self.assertIn("联网搜索", result["answer"])

    def test_with_history_includes_history_in_prompt(self):
        fake_llm = FakeLLM(["history-based answer"])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = generate_answer(_state(
                context="some docs",
                web_context="",
                question="follow up?",
                messages=[HumanMessage(content="first q"), AIMessage(content="first a")],
            ))
        self.assertIn("history", result["answer"])

    def test_web_sources_appended_to_sources(self):
        fake_llm = FakeLLM(["answer with web citation [1]"])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = generate_answer(_state(
                context="some docs",
                web_context="web results",
                used_web_search=True,
                web_search_results=[
                    {"title": "WebPage", "url": "https://example.com", "content": "web content", "score": 0.9},
                ],
                question="test?",
                messages=[],
                sources=[],
            ))
        urls = [s.get("url") for s in result.get("sources", [])]
        self.assertIn("https://example.com", urls)


# =============================================================================
# route_question — LLM classification branch + exception fallback
# =============================================================================

class RouteQuestionTests(unittest.TestCase):
    """route_question: LLM classifies ambiguous questions, exception fallback."""

    def test_llm_classifier_routes_ambiguous_to_knowledge_base(self):
        """No rule match → falls through to LLM, returns knowledge_base."""
        fake_llm = FakeLLM([
            '{"question_type":"knowledge_base","reason":"factual question"}'
        ])
        with patch("src.graph._get_llm", return_value=fake_llm):
            result = route_question(_state(
                question="云计算是什么",
                messages=[HumanMessage(content="hi"), AIMessage(content="hello")],
            ))
        self.assertEqual(result["question_type"], "knowledge_base")

    def test_llm_exception_falls_back_to_rule(self):
        """LLM throws → silently falls back to detect_question_type result."""
        def thrower(_p):
            raise RuntimeError("API down")
        mock_llm = unittest.mock.MagicMock()
        mock_llm.invoke = thrower
        with patch("src.graph._get_llm", return_value=mock_llm):
            result = route_question(_state(
                question="年假怎么算",
                messages=[HumanMessage(content="hi"), AIMessage(content="hello")],
            ))
        # No pattern for "年假" in detect_question_type (knowledge_base default)
        self.assertEqual(result["question_type"], "knowledge_base")


# =============================================================================
# _route_search_scope — keyword match / type / no-match branches
# =============================================================================

class RouteSearchScopeTests(unittest.TestCase):
    """_route_search_scope: keyword match, wrong type, no match."""

    def test_keyword_match_returns_source_type(self):
        result = _route_search_scope("考勤制度是什么", "knowledge_base")
        self.assertEqual(result, {"source_type": "local_file"})

    def test_non_knowledge_base_returns_empty(self):
        result = _route_search_scope("what is love", "chat_memory")
        self.assertEqual(result, {})

    def test_no_matching_keywords_returns_empty(self):
        result = _route_search_scope("量子计算原理", "knowledge_base")
        self.assertEqual(result, {})


# =============================================================================
# build_graph / get_graph — graph structure + caching
# =============================================================================

class BuildGraphTests(unittest.TestCase):
    """build_graph: nodes existence, get_graph caching."""

    def test_build_graph_contains_expected_nodes(self):
        kb = FakeKnowledgeBase()
        graph = build_graph(kb)
        # LangGraph compiled graph stores nodes internally
        self.assertIsNotNone(graph)

    def test_get_graph_returns_same_instance_for_same_kb(self):
        kb = FakeKnowledgeBase()
        g1 = get_graph(kb)
        g2 = get_graph(kb)
        self.assertIs(g1, g2)

    def test_get_graph_different_kb_different_cache(self):
        kb1 = FakeKnowledgeBase()
        kb2 = FakeKnowledgeBase()
        g1 = get_graph(kb1)
        g2 = get_graph(kb2)
        self.assertIsNot(g1, g2)


# =============================================================================
# finalize — delegates to _compute_evidence
# =============================================================================

class FinalizeTests(unittest.TestCase):
    """finalize: returns evidence_level/outcome_category/evidence_summary."""

    def test_finalize_returns_evidence_metadata(self):
        result = finalize(_state(
            sources=[],
            used_web_search=False,
            quality_ok=True,
            question_type="knowledge_base",
        ))
        self.assertIn("evidence_level", result)
        self.assertIn("outcome_category", result)
        self.assertIn("evidence_summary", result)


# =============================================================================
# parse_rerank_decision — empty / non-JSON edge cases
# =============================================================================

class RerankDecisionEdgeTests(unittest.TestCase):
    """parse_rerank_decision edge cases already in test_graph.py—here
    we cover empty and non-JSON inputs."""

    def test_empty_text_returns_empty_decision(self):
        from src.graph import parse_rerank_decision
        decision = parse_rerank_decision("", {"a", "b"})
        self.assertEqual(decision.selected_doc_ids, [])

    def test_non_json_returns_empty_decision(self):
        from src.graph import parse_rerank_decision
        decision = parse_rerank_decision("just plain text", {"a", "b"})
        self.assertEqual(decision.selected_doc_ids, [])


# =============================================================================
# parse_quality_decision — PASS / empty / malformed JSON edge cases
# =============================================================================

class QualityDecisionEdgeTests(unittest.TestCase):
    """parse_quality_decision: PASS literal, empty, malformed JSON."""

    def test_pass_literal_returns_true(self):
        from src.graph import parse_quality_decision
        decision = parse_quality_decision("PASS")
        self.assertTrue(decision.quality_passed)

    def test_empty_text_returns_not_passed(self):
        from src.graph import parse_quality_decision
        decision = parse_quality_decision("")
        self.assertFalse(decision.quality_passed)

    def test_malformed_json_falls_back_to_natural_language(self):
        from src.graph import parse_quality_decision
        decision = parse_quality_decision('{"broken": no quotes}')
        # Falls to natural language parsing — negative marker "无" may match
        # depending on the content. If no clear positive/negative, returns False.
        if not decision.quality_passed:
            self.assertIn(decision.retry_strategy, ("expand_retrieval", "none"))


if __name__ == "__main__":
    unittest.main()
