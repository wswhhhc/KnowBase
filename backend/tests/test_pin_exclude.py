import unittest
from unittest.mock import MagicMock

from langchain_core.documents import Document

from src.graph.nodes import retrieve_docs
from src.graph.state import GraphState
from src.rag.models import RetrievalResult


def _make_doc(chunk_id: str, content: str = "doc content") -> Document:
    return Document(
        page_content=content,
        metadata={"source": chunk_id.split(":")[0], "chunk_id": chunk_id},
    )


def _make_result(chunk_id: str, score: float = 0.5) -> RetrievalResult:
    return RetrievalResult(chunk_id=chunk_id, document=_make_doc(chunk_id), score=score)


class MockVectorStore:
    def __init__(self):
        self.get = MagicMock(return_value={"ids": [], "documents": [], "metadatas": []})


class MockKB:
    """Mock KnowledgeBase for testing retrieve_docs pin/exclude logic."""

    def __init__(self):
        self.vector_store = MockVectorStore()
        self._hybrid_results: list[RetrievalResult] = []
        self._neighbor_map: dict[str, list[Document]] = {}

    def set_hybrid_results(self, results: list[RetrievalResult]):
        self._hybrid_results = results

    def set_neighbors(self, neighbors: dict[str, list[Document]]):
        self._neighbor_map = neighbors

    def hybrid_search(self, query, k, score_threshold=None, filter=None) -> list[RetrievalResult]:
        return self._hybrid_results

    def get_neighbor_chunks(self, chunk_id: str, window: int = 1) -> list[Document]:
        return self._neighbor_map.get(chunk_id, [])


class RetrieveDocsPinExcludeTests(unittest.TestCase):
    """Regression tests for pin/exclude logic in retrieve_docs."""

    def _call_retrieve(self, kb, pinned: list[str] | None = None, excluded: list[str] | None = None) -> dict:
        state: GraphState = {
            "question": "test",
            "messages": [],
            "question_type": "knowledge_base",
            "rewritten_question": "",
            "documents": [],
            "context": "",
            "answer": "",
            "sources": [],
            "retry_count": 0,
            "retrieval_k": 5,
            "score_threshold": None,
            "quality_ok": True,
            "quality_reason": "",
            "retry_strategy": "none",
            "web_search_results": [],
            "web_context": "",
            "web_search_error": "",
            "used_web_search": False,
            "web_search_enabled": False,
            "search_strategy": "balanced",
            "search_filter": {},
            "pinned_chunk_ids": pinned or [],
            "excluded_chunk_ids": excluded or [],
            "evidence_level": "none",
            "evidence_summary": "",
            "outcome_category": "success",
            "used_rerank": False,
            "used_rewrite": False,
        }
        return retrieve_docs(state, kb)

    def test_excluded_chunks_removed_from_results(self):
        """Excluded chunks are filtered out after hybrid_search."""
        kb = MockKB()
        kb.set_hybrid_results([
            _make_result("doc.txt:0:a"),
            _make_result("doc.txt:1:b"),
            _make_result("bad.txt:0:x"),
        ])
        kb.set_neighbors({})

        result = self._call_retrieve(kb, excluded=["bad.txt:0:x"])
        source_ids = [s["chunk_id"] for s in result["sources"]]
        self.assertNotIn("bad.txt:0:x", source_ids)
        self.assertIn("doc.txt:0:a", source_ids)

    def test_excluded_chunks_not_reintroduced_by_neighbors(self):
        """Excluded chunks don't sneak back through neighbor expansion."""
        kb = MockKB()
        doc_a = _make_doc("main.txt:0:a")
        doc_b = _make_doc("excluded.txt:0:x")  # excluded
        kb.set_hybrid_results([
            RetrievalResult(chunk_id="main.txt:0:a", document=doc_a, score=0.5),
        ])
        # main.txt:0:a has excluded.txt:0:x as neighbor
        kb.set_neighbors({"main.txt:0:a": [doc_a, doc_b]})

        result = self._call_retrieve(kb, excluded=["excluded.txt:0:x"])
        source_ids = [s["chunk_id"] for s in result["sources"]]
        self.assertIn("main.txt:0:a", source_ids)
        self.assertNotIn("excluded.txt:0:x", source_ids)

    def test_pinned_chunks_included_from_vector_store(self):
        """Pinned chunks are fetched from vector_store.get() even if not in top-K."""
        kb = MockKB()
        kb.set_hybrid_results([
            _make_result("doc.txt:0:a"),
            _make_result("doc.txt:1:b"),
        ])
        kb.set_neighbors({})

        # Mock vector_store.get to return the pinned chunk
        pinned_doc = _make_doc("pinned.txt:0:p", "important pinned content")
        kb.vector_store.get.return_value = {
            "ids": ["pinned.txt:0:p"],
            "documents": [pinned_doc.page_content],
            "metadatas": [pinned_doc.metadata],
        }

        result = self._call_retrieve(kb, pinned=["pinned.txt:0:p"])
        source_ids = [s["chunk_id"] for s in result["sources"]]
        self.assertIn("pinned.txt:0:p", source_ids)

    def test_pinned_chunks_vector_store_get_called(self):
        """vector_store.get is called with the expected pinned IDs."""
        kb = MockKB()
        kb.set_hybrid_results([_make_result("doc.txt:0:a")])
        kb.set_neighbors({})

        self._call_retrieve(kb, pinned=["remote.txt:0:r"])

        kb.vector_store.get.assert_called_once()
        call_kwargs = kb.vector_store.get.call_args[1]
        self.assertIn("remote.txt:0:r", call_kwargs.get("ids", []))

    def test_empty_pinned_excluded_no_effect(self):
        """Empty pin/exclude lists don't modify normal retrieval."""
        kb = MockKB()
        kb.set_hybrid_results([
            _make_result("a.txt:0:x"),
            _make_result("a.txt:1:y"),
        ])
        kb.set_neighbors({})

        result = self._call_retrieve(kb)
        source_ids = [s["chunk_id"] for s in result["sources"]]
        self.assertEqual(len(source_ids), 2)

    def test_short_entity_query_boosts_exact_content_matches(self):
        kb = MockKB()
        ai_doc = Document(
            page_content="人工智能技术简介。",
            metadata={"source": "sample_ai.txt", "chunk_id": "sample_ai.txt:0:a"},
        )
        xiyou_doc = Document(
            page_content="孙悟空保护唐僧西天取经，二人是师徒关系。",
            metadata={"source": "sample_西游记.txt", "chunk_id": "sample_西游记.txt:22:x", "section": "西游记人物关系"},
        )
        kb.set_hybrid_results([
            RetrievalResult(chunk_id="sample_ai.txt:0:a", document=ai_doc, score=0.6),
            RetrievalResult(chunk_id="sample_西游记.txt:22:x", document=xiyou_doc, score=0.4),
        ])
        kb.set_neighbors({})

        state = retrieve_docs({
            **{
                "question": "孙悟空和唐僧什么关系",
                "messages": [],
                "question_type": "knowledge_base",
                "rewritten_question": "",
                "documents": [],
                "context": "",
                "answer": "",
                "sources": [],
                "retry_count": 0,
                "retrieval_k": 5,
                "score_threshold": None,
                "quality_ok": True,
                "quality_reason": "",
                "retry_strategy": "none",
                "web_search_results": [],
                "web_context": "",
                "web_search_error": "",
                "used_web_search": False,
                "web_search_enabled": False,
                "search_strategy": "balanced",
                "search_filter": {},
                "pinned_chunk_ids": [],
                "excluded_chunk_ids": [],
                "evidence_level": "none",
                "evidence_summary": "",
                "outcome_category": "success",
                "used_rerank": False,
                "used_rewrite": False,
            }
        }, kb)
        self.assertEqual(state["sources"][0]["source"], "sample_西游记.txt")

    def test_query_mentioning_source_name_boosts_source_title_match(self):
        kb = MockKB()
        manual_doc = Document(
            page_content="考勤制度与打卡说明。",
            metadata={"source": "员工手册_考勤与办公规范.md", "chunk_id": "员工手册_考勤与办公规范.md:0:m"},
        )
        xiyou_doc = Document(
            page_content="《西游记》中妖怪故事很多。",
            metadata={"source": "sample_西游记.txt", "chunk_id": "sample_西游记.txt:17:y", "section": "西游记中的妖怪"},
        )
        kb.set_hybrid_results([
            RetrievalResult(chunk_id="员工手册_考勤与办公规范.md:0:m", document=manual_doc, score=0.55),
            RetrievalResult(chunk_id="sample_西游记.txt:17:y", document=xiyou_doc, score=0.45),
        ])
        kb.set_neighbors({})

        state = retrieve_docs({
            "question": "西游记有多少只妖怪",
            "messages": [],
            "question_type": "knowledge_base",
            "rewritten_question": "",
            "documents": [],
            "context": "",
            "answer": "",
            "sources": [],
            "retry_count": 0,
            "retrieval_k": 5,
            "score_threshold": None,
            "quality_ok": True,
            "quality_reason": "",
            "retry_strategy": "none",
            "web_search_results": [],
            "web_context": "",
            "web_search_error": "",
            "used_web_search": False,
            "web_search_enabled": False,
            "search_strategy": "balanced",
            "search_filter": {},
            "pinned_chunk_ids": [],
            "excluded_chunk_ids": [],
            "evidence_level": "none",
            "evidence_summary": "",
            "outcome_category": "success",
            "used_rerank": False,
            "used_rewrite": False,
        }, kb)
        self.assertEqual(state["sources"][0]["source"], "sample_西游记.txt")


if __name__ == "__main__":
    unittest.main()
