"""Extended tests for src.knowledge_base — neighbor chunks, clear, rrf_fuse, content_hash."""
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from src.knowledge_base import KnowledgeBase, _content_hash, _document_chunk_id, rrf_fuse


class NeighborChunksTests(unittest.TestCase):
    def setUp(self):
        patcher1 = patch("src.knowledge_base.require_siliconflow_api_key", return_value="sk-test")
        patcher2 = patch("src.knowledge_base.OpenAIEmbeddings")
        patcher3 = patch("src.knowledge_base.Chroma")
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)
        self.addCleanup(patcher3.stop)
        patcher1.start()
        patcher2.start()
        mock_chroma = patcher3.start()

        self.mock_chroma_instance = MagicMock()
        self.mock_chroma_instance.get.return_value = {
            "documents": [], "metadatas": [], "ids": [],
        }
        mock_chroma.return_value = self.mock_chroma_instance
        self.kb = KnowledgeBase()
        self.kb._loaded = True

        self.kb.all_docs = [
            Document(
                page_content="chunk0",
                metadata={"source": "doc.txt", "chunk_id": "doc.txt:0:aaa", "chunk_index": 0},
            ),
            Document(
                page_content="chunk1",
                metadata={"source": "doc.txt", "chunk_id": "doc.txt:1:bbb", "chunk_index": 1},
            ),
            Document(
                page_content="chunk2",
                metadata={"source": "doc.txt", "chunk_id": "doc.txt:2:ccc", "chunk_index": 2},
            ),
            Document(
                page_content="other_chunk",
                metadata={"source": "other.txt", "chunk_id": "other.txt:0:ddd", "chunk_index": 0},
            ),
        ]
        self.kb._rebuild_all()

    def test_get_neighbor_chunks_returns_adjacent_chunks_with_default_window(self):
        neighbors = self.kb.get_neighbor_chunks("doc.txt:1:bbb", window=1)
        ids = [d.metadata["chunk_id"] for d in neighbors]
        self.assertIn("doc.txt:0:aaa", ids)
        self.assertIn("doc.txt:1:bbb", ids)
        self.assertIn("doc.txt:2:ccc", ids)
        self.assertEqual(len(ids), 3)

    def test_get_neighbor_chunks_window_zero_returns_only_target(self):
        neighbors = self.kb.get_neighbor_chunks("doc.txt:1:bbb", window=0)
        self.assertEqual(len(neighbors), 1)
        self.assertEqual(neighbors[0].metadata["chunk_id"], "doc.txt:1:bbb")

    def test_get_neighbor_chunks_first_chunk_no_left_neighbor(self):
        neighbors = self.kb.get_neighbor_chunks("doc.txt:0:aaa", window=1)
        ids = [d.metadata["chunk_id"] for d in neighbors]
        self.assertEqual(ids, ["doc.txt:0:aaa", "doc.txt:1:bbb"])

    def test_get_neighbor_chunks_last_chunk_no_right_neighbor(self):
        neighbors = self.kb.get_neighbor_chunks("doc.txt:2:ccc", window=1)
        ids = [d.metadata["chunk_id"] for d in neighbors]
        self.assertEqual(ids, ["doc.txt:1:bbb", "doc.txt:2:ccc"])

    def test_get_neighbor_chunks_non_existent_returns_empty(self):
        neighbors = self.kb.get_neighbor_chunks("nonexistent:0:xxx", window=1)
        self.assertEqual(neighbors, [])

    def test_get_neighbor_chunks_window_larger_than_corpus(self):
        neighbors = self.kb.get_neighbor_chunks("doc.txt:0:aaa", window=10)
        self.assertEqual(len(neighbors), 3)  # Only 3 docs in the source


class ClearTests(unittest.TestCase):
    def setUp(self):
        patcher1 = patch("src.knowledge_base.require_siliconflow_api_key", return_value="sk-test")
        patcher2 = patch("src.knowledge_base.OpenAIEmbeddings")
        patcher3 = patch("src.knowledge_base.Chroma")
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)
        self.addCleanup(patcher3.stop)
        patcher1.start()
        patcher2.start()
        mock_chroma = patcher3.start()

        self.mock_chroma_instance = MagicMock()
        self.mock_chroma_instance.get.return_value = {
            "documents": [], "metadatas": [], "ids": [],
        }
        mock_chroma.return_value = self.mock_chroma_instance
        self.kb = KnowledgeBase()

    def test_clear_resets_all_state(self):
        self.kb._loaded = True
        self.kb.all_docs = [Document(page_content="test", metadata={"chunk_id": "x:0:y", "source": "x"})]
        self.kb._rebuild_all()
        self.kb.hit_counter = {"x:0:y": 5}

        self.kb.clear()

        self.assertFalse(self.kb._loaded)
        self.assertEqual(self.kb.all_docs, [])
        self.assertEqual(self.kb.doc_by_id, {})
        self.assertEqual(len(self.kb.existing_chunk_ids), 0)
        self.assertIsNone(self.kb.bm25_index)
        self.assertEqual(self.kb.hit_counter, {})

    def test_clear_after_no_load_is_safe(self):
        """Calling clear when KB was never loaded should not raise."""
        try:
            self.kb.clear()
        except Exception as e:
            self.fail(f"clear raised {e}")


class ContentHashTests(unittest.TestCase):
    def test_content_hash_is_consistent(self):
        h1 = _content_hash("同一个内容")
        h2 = _content_hash("同一个内容")
        self.assertEqual(h1, h2)

    def test_content_hash_differs_for_different_content(self):
        h1 = _content_hash("内容A")
        h2 = _content_hash("内容B")
        self.assertNotEqual(h1, h2)

    def test_content_hash_is_deterministic_sha256_hex(self):
        h = _content_hash("测试")
        self.assertEqual(len(h), 64)  # SHA-256 hex is 64 chars
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class RRFFuseEdgeCaseTests(unittest.TestCase):
    def test_rrf_fuse_with_empty_inputs_returns_empty(self):
        fused = rrf_fuse(vector_ranked=[], bm25_ranked=[], limit=10)
        self.assertEqual(fused, [])

    def test_rrf_fuse_with_limit_truncation(self):
        fused = rrf_fuse(
            vector_ranked=[("a", 0.9), ("b", 0.8), ("c", 0.7)],
            bm25_ranked=[("a", 5.0)],
            limit=1,
        )
        self.assertEqual(len(fused), 1)

    def test_rrf_fuse_empty_vector_but_bm25(self):
        fused = rrf_fuse(
            vector_ranked=[],
            bm25_ranked=[("x", 3.0), ("y", 2.0)],
            limit=5,
        )
        self.assertEqual(len(fused), 2)
        self.assertEqual(fused[0].chunk_id, "x")
        self.assertEqual(fused[1].chunk_id, "y")

    def test_rrf_fuse_empty_bm25_but_vector(self):
        fused = rrf_fuse(
            vector_ranked=[("x", 0.5), ("y", 0.4)],
            bm25_ranked=[],
            limit=5,
        )
        self.assertEqual(len(fused), 2)
        self.assertEqual(fused[0].chunk_id, "x")
        self.assertEqual(fused[1].chunk_id, "y")

    def test_rrf_fuse_ordering_score_descending(self):
        fused = rrf_fuse(
            vector_ranked=[("a", 0.9), ("b", 0.8)],
            bm25_ranked=[("c", 5.0), ("b", 3.0)],
            limit=3,
        )
        scores = [item.score for item in fused]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_rrf_fuse_vector_and_bm25_scores_preserved(self):
        fused = rrf_fuse(
            vector_ranked=[("a", 0.9)],
            bm25_ranked=[("a", 5.0)],
            limit=1,
        )
        self.assertEqual(fused[0].vector_score, 0.9)
        self.assertEqual(fused[0].bm25_score, 5.0)

    def test_rrf_fuse_no_duplicates(self):
        fused = rrf_fuse(
            vector_ranked=[("a", 0.9), ("b", 0.8)],
            bm25_ranked=[("a", 5.0), ("b", 4.0)],
            limit=2,
        )
        chunk_ids = [item.chunk_id for item in fused]
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))


class DocumentChunkIdTests(unittest.TestCase):
    def test_document_chunk_id_backfills_legacy_metadata(self):
        doc = Document(page_content="legacy", metadata={"source": "old.txt", "chunk_index": 2})
        chunk_id = _document_chunk_id(doc)
        self.assertTrue(chunk_id.startswith("old.txt:2:"))
        self.assertEqual(doc.metadata["chunk_id"], chunk_id)

    def test_document_chunk_id_uses_existing_id(self):
        doc = Document(page_content="test", metadata={"chunk_id": "custom:0:id"})
        result = _document_chunk_id(doc)
        self.assertEqual(result, "custom:0:id")


if __name__ == "__main__":
    unittest.main()
