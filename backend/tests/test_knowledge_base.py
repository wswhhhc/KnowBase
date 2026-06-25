"""Extended tests for src.knowledge_base — neighbor chunks, clear, rrf_fuse, content_hash."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from langchain_core.documents import Document

from src.knowledge_base import (
    IngestionService,
    KnowledgeBase,
    rrf_fuse,
)
from src.kb_models import (
    compute_content_hash as _content_hash,
    document_chunk_id as _document_chunk_id,
    infer_source_type as _infer_source_type,
    normalize_source,
)


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
        self.kb.ingestion._loaded = True

        self.kb.all_docs[:] = [
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
        self.kb.ingestion._rebuild_all()

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
        self.kb.ingestion._loaded = True
        self.kb.all_docs[:] = [Document(page_content="test", metadata={"chunk_id": "x:0:y", "source": "x"})]
        self.kb.ingestion._rebuild_all()
        self.kb.hotspots.hit_counter = {"x:0:y": 5}

        self.kb.clear()

        self.assertFalse(self.kb.ingestion._loaded)
        self.assertEqual(self.kb.all_docs, [])
        self.assertEqual(self.kb.doc_by_id, {})
        self.assertEqual(len(self.kb.existing_chunk_ids), 0)
        self.assertIsNone(self.kb.ingestion._bm25_index[0])
        self.assertEqual(self.kb.hotspots.hit_counter, {})

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

    def test_document_chunk_id_repairs_legacy_url_chunk_id(self):
        doc = Document(
            page_content="content",
            metadata={
                "source": "index.html",
                "url": "https://foo.com/docs/index.html",
                "chunk_index": 0,
                "chunk_id": "index.html:0:oldbadid12345678",
            },
        )
        result = _document_chunk_id(doc)
        self.assertTrue(result.startswith("https://foo.com/docs/index.html:0:"))
        self.assertEqual(doc.metadata["source"], "https://foo.com/docs/index.html")
        self.assertEqual(doc.metadata["legacy_chunk_id"], "index.html:0:oldbadid12345678")


class LegacyChromaMigrationTests(unittest.TestCase):
    def test_documents_from_chroma_result_upgrades_legacy_url_source(self):
        result = {
            "documents": ["content"],
            "metadatas": [{
                "source": "index.html",
                "url": "https://foo.com/docs/index.html",
                "chunk_index": 0,
            }],
            "ids": ["legacy-row-id"],
        }

        docs = IngestionService._documents_from_chroma_result(result)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "https://foo.com/docs/index.html")

    def test_documents_from_chroma_result_rebuilds_legacy_url_chunk_id(self):
        result = {
            "documents": ["content"],
            "metadatas": [{
                "source": "index.html",
                "url": "https://foo.com/docs/index.html",
                "chunk_index": 0,
                "chunk_id": "index.html:0:oldbadid12345678",
            }],
            "ids": ["legacy-row-id"],
        }

        docs = IngestionService._documents_from_chroma_result(result)

        self.assertEqual(len(docs), 1)
        migrated = docs[0].metadata
        self.assertEqual(migrated["source"], "https://foo.com/docs/index.html")
        self.assertTrue(migrated["chunk_id"].startswith("https://foo.com/docs/index.html:0:"))
        self.assertEqual(migrated["legacy_chunk_id"], "index.html:0:oldbadid12345678")


class NormalizeSourceTests(unittest.TestCase):
    """Test normalize_source — URL vs file path distinction."""

    def test_url_preserved_as_is(self):
        self.assertEqual(normalize_source("https://example.com/page"), "https://example.com/page")

    def test_url_with_trailing_slash(self):
        self.assertEqual(normalize_source("https://site.com/docs/"), "https://site.com/docs/")

    def test_url_with_path_and_query(self):
        self.assertEqual(normalize_source("https://blog.example/posts/2025?id=1"), "https://blog.example/posts/2025?id=1")

    def test_local_file_takes_basename(self):
        self.assertEqual(normalize_source("/home/user/docs/report.pdf"), "report.pdf")

    def test_local_file_windows_path(self):
        self.assertEqual(normalize_source("C:\\Users\\me\\doc.txt"), "doc.txt")

    def test_relative_path_takes_basename(self):
        self.assertEqual(normalize_source("./data/sample.txt"), "sample.txt")

    def test_plain_filename_stays_unchanged(self):
        self.assertEqual(normalize_source("readme.md"), "readme.md")

    def test_different_urls_same_basename_dont_collide(self):
        url_a = normalize_source("https://foo.com/docs/index.html")
        url_b = normalize_source("https://bar.com/docs/index.html")
        self.assertNotEqual(url_a, url_b)
        self.assertEqual(url_a, "https://foo.com/docs/index.html")
        self.assertEqual(url_b, "https://bar.com/docs/index.html")


# ---- NEW TEST CLASSES BELOW ----

class TokenizeTests(unittest.TestCase):
    """Test IngestionService._tokenize static method."""

    def test_chinese_text_returns_segmented_tokens(self):
        tokens = IngestionService._tokenize("我爱北京天安门")
        self.assertGreater(len(tokens), 2)
        for t in tokens:
            self.assertIsInstance(t, str)
            self.assertEqual(t, t.strip())
            self.assertEqual(t, t.lower())

    def test_mixed_chinese_english(self):
        tokens = IngestionService._tokenize("Hello世界测试")
        self.assertTrue(any("hello" in t for t in tokens))
        self.assertTrue(any("世界" in t for t in tokens))
        self.assertTrue(any("测试" in t for t in tokens))

    def test_empty_string_returns_empty_list(self):
        tokens = IngestionService._tokenize("")
        self.assertEqual(tokens, [])

    def test_only_whitespace_returns_empty_list(self):
        tokens = IngestionService._tokenize("   \n\t  ")
        self.assertEqual(tokens, [])


class InferSourceTypeTests(unittest.TestCase):
    """Test module-level _infer_source_type function."""

    def test_http_url_returns_web_page(self):
        self.assertEqual(_infer_source_type("http://example.com/doc"), "web_page")

    def test_https_url_returns_web_page(self):
        self.assertEqual(_infer_source_type("https://example.com/doc"), "web_page")

    def test_local_file_path_returns_local_file(self):
        self.assertEqual(_infer_source_type("data/sample.txt"), "local_file")

    def test_empty_string_returns_local_file(self):
        self.assertEqual(_infer_source_type(""), "local_file")

    def test_relative_path_returns_local_file(self):
        self.assertEqual(_infer_source_type("./docs/readme.md"), "local_file")


class PrepareSplitsTests(unittest.TestCase):
    """Test IngestionService._prepare_splits static method."""

    def test_normal_split_produces_chunk_id_metadata(self):
        docs = [Document(page_content="这是一个测试文档。" * 200, metadata={"source": "test.txt"})]
        splits = IngestionService._prepare_splits(docs)
        self.assertGreater(len(splits), 0)
        for split in splits:
            self.assertIn("chunk_id", split.metadata)
            self.assertIn("chunk_index", split.metadata)
            self.assertIn("content_hash", split.metadata)
            self.assertIn("source", split.metadata)
            self.assertIn("source_type", split.metadata)
            self.assertTrue(split.metadata["chunk_id"].startswith("test.txt:"))

    def test_heading_detection_sets_section_metadata(self):
        content = "# 一级标题\n\n第一段内容\n\n## 二级标题\n\n第二段内容"
        docs = [Document(page_content=content, metadata={"source": "heading_test.txt"})]
        splits = IngestionService._prepare_splits(docs)
        sections = [s.metadata.get("section", "") for s in splits]
        self.assertTrue(any(sections))

    def test_contextual_retrieval_prefix_when_enabled(self):
        """ENABLE_CONTEXTUAL_RETRIEVAL is True by default in config, so
        _prepare_splits should prepend context prefix."""
        docs = [Document(page_content="小明去公园玩。" * 200, metadata={"source": "story.txt"})]
        splits = IngestionService._prepare_splits(docs)
        for split in splits:
            self.assertIn("本段属于文档", split.page_content)
            # The original content should be preserved in metadata
            self.assertIn("original_content", split.metadata)

    def test_empty_docs_returns_empty(self):
        splits = IngestionService._prepare_splits([])
        self.assertEqual(splits, [])

    def test_multiple_splits_from_same_source_get_increasing_chunk_index(self):
        docs = [Document(page_content="测试内容。" * 500, metadata={"source": "same_source.txt"})]
        splits = IngestionService._prepare_splits(docs)
        indices = [s.metadata["chunk_index"] for s in splits]
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(len(indices), len(set(indices)))


class _BaseKBMockTest(unittest.TestCase):
    """Base class for tests needing a mocked KnowledgeBase with loaded state."""

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
        self.kb.ingestion._loaded = True
        self.kb.all_docs[:] = [
            Document(
                page_content="existing chunk content",
                metadata={
                    "source": "existing.txt",
                    "chunk_id": "existing.txt:0:abc123",
                    "chunk_index": 0,
                    "content_hash": "abc123",
                    "source_type": "local_file",
                },
            ),
        ]
        self.kb.ingestion._rebuild_all()
        # Reset hit_counter after _rebuild_all
        self.kb.hotspots.hit_counter = {}


class ProcessDocumentsTests(_BaseKBMockTest):
    """Test _process_documents with mocked KB."""

    def test_new_docs_get_processed_and_extend_all_docs(self):
        new_docs = [
            Document(page_content="全新的文档内容" * 100, metadata={"source": "new_file.txt"}),
        ]
        count = self.kb.ingestion._process_documents(new_docs)
        self.assertGreater(count, 0)
        self.assertEqual(count, len(self.kb.all_docs) - 1)  # minus the existing doc

    def test_duplicate_chunks_are_skipped(self):
        """Re-processing the same doc should return 0 new chunks."""
        docs = [
            Document(page_content="第一次添加" * 50, metadata={"source": "dup_test.txt"}),
        ]
        count1 = self.kb.ingestion._process_documents(docs)
        self.assertGreater(count1, 0)

        # Process the exact same docs again
        count2 = self.kb.ingestion._process_documents(docs)
        self.assertEqual(count2, 0)

    def test_first_ingestion_calls_ensure_loaded(self):
        """_process_documents calls _ensure_loaded before adding new docs."""
        self.kb.ingestion._loaded = False
        self.kb.all_docs.clear()
        self.kb.ingestion._rebuild_all()

        docs = [
            Document(page_content="首次添加" * 50, metadata={"source": "first_test.txt"}),
        ]
        count = self.kb.ingestion._process_documents(docs)
        self.assertGreater(count, 0)
        self.assertTrue(self.kb.ingestion._loaded)


class HybridSearchTests(_BaseKBMockTest):
    """Test hybrid_search with mocked vector store."""

    def setUp(self):
        super().setUp()

        # Controlled vector results: list of (Document, float) tuples
        self.mock_vector_results = [
            (
                Document(
                    page_content="这是关于人工智能的文档内容",
                    metadata={
                        "source": "ai.txt",
                        "chunk_id": "ai.txt:0:hash1",
                        "chunk_index": 0,
                    },
                ),
                0.85,
            ),
            (
                Document(
                    page_content="机器学习的进阶内容",
                    metadata={
                        "source": "ml.txt",
                        "chunk_id": "ml.txt:0:hash2",
                        "chunk_index": 0,
                    },
                ),
                0.72,
            ),
        ]

        # Register these docs so they exist in doc_by_id
        for doc, _score in self.mock_vector_results:
            if doc.metadata["chunk_id"] not in self.kb.doc_by_id:
                self.kb.all_docs.append(doc)
                self.kb.doc_by_id[doc.metadata["chunk_id"]] = doc
        self.kb.existing_chunk_ids.clear()
        self.kb.existing_chunk_ids.update(self.kb.doc_by_id)

        self.kb.vector_store.similarity_search_with_score.return_value = self.mock_vector_results

    def test_vector_only_search_when_bm25_is_none(self):
        """When bm25_index is None, results come only from vector_store."""
        self.kb.ingestion._bm25_index[0] = None
        results = self.kb.hybrid_search("人工智能")
        self.assertGreater(len(results), 0)
        # The score_threshold is None by default, so no filtering
        self.kb.vector_store.similarity_search_with_score.assert_called_with(
            "人工智能", k=unittest.mock.ANY, filter=None
        )

    def test_search_with_empty_kb_returns_empty(self):
        """When KB has no documents, search returns empty."""
        self.kb.all_docs.clear()
        self.kb.doc_by_id.clear()
        self.kb.existing_chunk_ids.clear()
        self.kb.ingestion._bm25_index[0] = None
        self.kb.vector_store.similarity_search_with_score.return_value = []
        results = self.kb.hybrid_search("anything")
        self.assertEqual(results, [])

    def test_filter_parameter_passed_to_vector_store(self):
        results = self.kb.hybrid_search("人工智能", filter={"source": "ai.txt"})
        call_kwargs = self.kb.vector_store.similarity_search_with_score.call_args
        self.assertIsNotNone(call_kwargs)
        _, kwargs = call_kwargs
        self.assertEqual(kwargs.get("filter"), {"source": "ai.txt"})

    def test_search_calls_ensure_loaded(self):
        """Verify hybrid_search triggers _ensure_loaded."""
        self.kb.ingestion._loaded = False
        results = self.kb.hybrid_search("测试查询")
        self.assertTrue(self.kb.ingestion._loaded)

    def test_score_threshold_filters_results(self):
        """score_threshold should remove results below the threshold."""
        results = self.kb.hybrid_search("test", score_threshold=0.8)
        for r in results:
            self.assertGreaterEqual(r.score, 0.8)

    def test_retrieval_result_has_correct_fields(self):
        results = self.kb.hybrid_search("人工智能")
        self.assertGreater(len(results), 0)
        r = results[0]
        self.assertIsNotNone(r.chunk_id)
        self.assertIsNotNone(r.document)
        self.assertIsNotNone(r.score)
        # vector_score and bm25_score can be None


class GetHotspotsTests(_BaseKBMockTest):
    """Test get_hotspots."""

    def setUp(self):
        super().setUp()

        # Add more docs for hotspot testing
        extra_docs = [
            Document(
                page_content="热点文档A",
                metadata={
                    "source": "popular.txt",
                    "chunk_id": "popular.txt:0:hot1",
                    "chunk_index": 0,
                },
            ),
            Document(
                page_content="热点文档B",
                metadata={
                    "source": "popular.txt",
                    "chunk_id": "popular.txt:1:hot2",
                    "chunk_index": 1,
                },
            ),
        ]
        for doc in extra_docs:
            self.kb.all_docs.append(doc)
            self.kb.doc_by_id[doc.metadata["chunk_id"]] = doc
        self.kb.existing_chunk_ids.clear()
        self.kb.existing_chunk_ids.update(self.kb.doc_by_id)

    def test_with_hits_returns_sorted_by_hit_count(self):
        self.kb.hotspots.hit_counter = {
            "popular.txt:1:hot2": 10,
            "popular.txt:0:hot1": 5,
            "existing.txt:0:abc123": 1,
        }
        hotspots = self.kb.get_hotspots(top_n=50)
        self.assertGreater(len(hotspots), 0)
        hit_counts = [h.hits for h in hotspots]
        self.assertEqual(hit_counts, sorted(hit_counts, reverse=True))

    def test_empty_hit_counter_returns_empty_list(self):
        self.kb.hotspots.hit_counter = {}
        hotspots = self.kb.get_hotspots()
        self.assertEqual(hotspots, [])

    def test_top_n_limits_results(self):
        self.kb.hotspots.hit_counter = {
            "popular.txt:0:hot1": 5,
            "popular.txt:1:hot2": 3,
            "existing.txt:0:abc123": 1,
        }
        hotspots = self.kb.get_hotspots(top_n=2)
        self.assertEqual(len(hotspots), 2)

    def test_hit_for_chunk_not_in_doc_by_id_returns_empty_source_preview(self):
        self.kb.hotspots.hit_counter = {
            "nonexistent:0:ghost": 99,
        }
        hotspots = self.kb.get_hotspots()
        self.assertEqual(len(hotspots), 1)
        self.assertEqual(hotspots[0].source, "")
        self.assertEqual(hotspots[0].content_preview, "")

    def test_get_hotspots_works_after_explicit_ensure_loaded(self):
        self.kb.ingestion._loaded = False
        # Fake some hit_counter entries
        self.kb.hotspots.hit_counter = {"popular.txt:0:hot1": 3}
        self.kb.ingestion._ensure_loaded()
        hotspots = self.kb.get_hotspots()
        self.assertGreater(len(hotspots), 0)
        self.assertTrue(self.kb.ingestion._loaded)


class LoadSaveHotspotsTests(_BaseKBMockTest):
    """Test _load_hotspots and _save_hotspots."""

    def setUp(self):
        super().setUp()
        # Create a real temp file path instead of patching Path.exists
        self.tmp_hotspot = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        self.tmp_path = Path(self.tmp_hotspot.name)
        self.tmp_hotspot.close()

    def tearDown(self):
        self.tmp_path.unlink(missing_ok=True)

    def test_save_writes_to_file(self):
        self.kb.hotspots._hotspot_path = self.tmp_path
        self.kb.hotspots.hit_counter = {"chunk_a:0:id1": 5, "chunk_b:0:id2": 3}
        self.kb.hotspots._hotspot_dirty = True
        self.kb.hotspots._save_hotspots()

        with open(self.tmp_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, {"chunk_a:0:id1": 5, "chunk_b:0:id2": 3})

    def test_load_with_valid_json(self):
        data = {"test:0:id": 10, "other:1:id2": 7}
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        self.kb.hotspots._hotspot_path = self.tmp_path
        self.kb.hotspots.hit_counter = {}
        self.kb.hotspots._load_hotspots()
        self.assertEqual(self.kb.hotspots.hit_counter, data)

    def test_file_not_exists_leaves_counter_unchanged(self):
        # When the file doesn't exist, _load_hotspots does not modify hit_counter
        nonexistent = Path(tempfile.gettempdir()) / "_knowbase_test_nonexistent" / "hotspots.json"
        self.assertFalse(nonexistent.exists())
        self.kb.hotspots._hotspot_path = nonexistent
        self.kb.hotspots.hit_counter = {"old": 1}
        self.kb.hotspots._load_hotspots()
        # hit_counter unchanged because file doesn't exist and try/except catches nothing
        self.assertEqual(self.kb.hotspots.hit_counter, {"old": 1})


class ExtendBM25Tests(_BaseKBMockTest):
    """Test _extend_bm25."""

    def setUp(self):
        super().setUp()
        # Start with clean BM25
        self.kb.ingestion._bm25_corpus.clear()
        self.kb.ingestion._bm25_index[0] = None

    def test_adding_docs_rebuilds_bm25_index(self):
        docs = [
            Document(page_content="测试内容A", metadata={"source": "test.txt", "chunk_id": "test.txt:0:a"}),
            Document(page_content="测试内容B", metadata={"source": "test.txt", "chunk_id": "test.txt:1:b"}),
        ]
        self.kb.ingestion._extend_bm25(docs)
        self.assertIsNotNone(self.kb.ingestion._bm25_index[0])
        self.assertEqual(len(self.kb.ingestion._bm25_corpus), 2)

    def test_adding_to_empty_corpus_sets_bm25_to_none_if_still_empty(self):
        # _extend_bm25 with empty list should not build index from empty corpus
        self.kb.ingestion._extend_bm25([])
        self.assertIsNone(self.kb.ingestion._bm25_index[0])
        self.assertEqual(self.kb.ingestion._bm25_corpus, [])

    def test_extend_preserves_existing_corpus(self):
        initial = [
            Document(page_content="原文", metadata={"source": "a.txt", "chunk_id": "a.txt:0:0"}),
        ]
        self.kb.ingestion._extend_bm25(initial)
        original_len = len(self.kb.ingestion._bm25_corpus)

        more = [
            Document(page_content="新增内容", metadata={"source": "b.txt", "chunk_id": "b.txt:0:1"}),
        ]
        self.kb.ingestion._extend_bm25(more)
        self.assertEqual(len(self.kb.ingestion._bm25_corpus), original_len + 1)


class KnowledgeBaseIngestTests(_BaseKBMockTest):
    """Test ingest_file delegates correctly."""

    def test_ingest_file_delegates_to_load_document_and_process_documents(self):
        fake_docs = [
            Document(page_content="test", metadata={"source": "test.txt"}),
        ]
        with patch("src.knowledge_base.load_document", return_value=fake_docs) as mock_load:
            with patch.object(self.kb.ingestion, "_process_documents", return_value=1) as mock_process:
                result = self.kb.ingest_file("/fake/path/test.txt")

                mock_load.assert_called_once_with("/fake/path/test.txt", source_name=None)
                mock_process.assert_called_once_with(fake_docs)
                self.assertEqual(result, 1)

    def test_ingest_file_with_source_name(self):
        fake_docs = [
            Document(page_content="test", metadata={"source": "custom.txt"}),
        ]
        with patch("src.knowledge_base.load_document", return_value=fake_docs) as mock_load:
            with patch.object(self.kb.ingestion, "_process_documents", return_value=2) as mock_process:
                result = self.kb.ingest_file("/fake/path/doc.pdf", source_name="my_doc.pdf")

                mock_load.assert_called_once_with("/fake/path/doc.pdf", source_name="my_doc.pdf")
                self.assertEqual(result, 2)

    def test_ingest_file_replaces_old_chunks_when_source_exists(self):
        """Re-uploading same source name removes old chunks from vector_store."""
        self.kb.all_docs.append(
            Document(
                page_content="stale content that will be replaced",
                metadata={
                    "source": "replaced.txt",
                    "chunk_id": "replaced.txt:0:oldhash1234",
                    "chunk_index": 0,
                    "content_hash": "oldhash1234",
                    "source_type": "local_file",
                },
            ),
        )
        self.kb.ingestion._rebuild_all()
        self.kb.vector_store.delete.reset_mock()

        fake_docs = [
            Document(page_content="全新的文档内容" * 100, metadata={"source": "replaced.txt"}),
        ]

        with patch("src.knowledge_base.load_document", return_value=fake_docs):
            result = self.kb.ingest_file("/fake/path/replaced.txt", source_name="replaced.txt")

        self.assertGreater(result, 0)
        # Stale chunk should be removed from in-memory state
        stale_id = "replaced.txt:0:oldhash1234"
        self.assertNotIn(stale_id, self.kb.doc_by_id)
        self.assertNotIn(stale_id, self.kb.existing_chunk_ids)
        self.assertFalse(
            any(d.metadata["chunk_id"] == stale_id for d in self.kb.all_docs)
        )

    def test_different_urls_same_basename_no_collision(self):
        """Two URLs with the same path basename must not interfere."""
        self.kb.all_docs.append(
            Document(
                page_content="content from foo.com",
                metadata={
                    "source": "https://foo.com/docs/index.html",
                    "chunk_id": "https://foo.com/docs/index.html:0:aaa111",
                    "chunk_index": 0,
                    "content_hash": "aaa111",
                },
            ),
        )
        self.kb.ingestion._rebuild_all()

        self.kb.vector_store.delete.reset_mock()

        url_b_docs = [
            Document(page_content="全" * 200, metadata={"source": "https://bar.com/docs/index.html"}),
        ]

        with patch("src.knowledge_base.load_document", return_value=url_b_docs):
            self.kb.ingest_file("/fake/path/page.html", source_name="https://bar.com/docs/index.html")

        # foo.com chunk must still be present
        self.assertIn("https://foo.com/docs/index.html:0:aaa111", self.kb.doc_by_id)
        self.assertIn("https://foo.com/docs/index.html:0:aaa111", self.kb.existing_chunk_ids)

        # bar.com old_ids is empty (first import), so _replace_old_chunks should
        # not have called delete at all — verifying delete was not invoked.
        # (delete was also called by _process_documents internally for dedup,
        #  so we verify foo.com chunk survived instead.)

    def test_replace_old_chunks_deletes_legacy_chroma_row_ids(self):
        stale = Document(
            page_content="old content",
            metadata={
                "source": "https://foo.com/docs/index.html",
                "chunk_id": "https://foo.com/docs/index.html:0:oldhash1234567890",
                "chunk_index": 0,
                "legacy_chroma_id": "uuid-1234",
            },
        )
        self.kb.all_docs.append(stale)
        self.kb.ingestion._rebuild_all()
        self.kb.vector_store.delete.reset_mock()

        fresh_docs = [
            Document(page_content="new content" * 100, metadata={"source": "https://foo.com/docs/index.html"}),
        ]

        self.kb.ingestion._replace_old_chunks("https://foo.com/docs/index.html", fresh_docs)

        self.kb.vector_store.delete.assert_called_once_with(ids=["uuid-1234"])

    def test_process_documents_dedups_against_loaded_canonical_chunk_ids(self):
        self.kb.ingestion._loaded = False
        self.kb.all_docs.clear()
        self.kb.doc_by_id.clear()
        self.kb.existing_chunk_ids.clear()
        self.kb.existing_chunk_ids.update(["legacy-uuid-row-id"])
        self.kb.vector_store.get.return_value = {
            "ids": ["legacy-uuid-row-id"],
            "documents": ["same content" * 100],
            "metadatas": [{
                "source": "same.txt",
                "chunk_index": 0,
                "url": "",
            }],
        }
        self.kb.vector_store.add_documents.reset_mock()

        docs = [
            Document(page_content="same content" * 100, metadata={"source": "same.txt"}),
        ]

        count = self.kb.ingestion._process_documents(docs)

        self.assertEqual(count, 0)
        self.kb.vector_store.add_documents.assert_not_called()


class KBEnsureLoadedTests(_BaseKBMockTest):
    """Test _ensure_loaded."""

    def test_already_loaded_returns_immediately(self):
        self.kb.ingestion._loaded = True
        self.kb.vector_store.get.reset_mock()
        self.kb.ingestion._ensure_loaded()
        self.kb.vector_store.get.assert_not_called()

    def test_not_loaded_calls_vector_store_get_and_rebuilds(self):
        self.kb.ingestion._loaded = False
        self.kb.all_docs.clear()
        self.kb.doc_by_id.clear()

        mock_result = {
            "ids": ["doc.txt:0:aaa", "doc.txt:1:bbb"],
            "documents": ["content1", "content2"],
            "metadatas": [
                {"source": "doc.txt", "chunk_index": 0, "chunk_id": "doc.txt:0:aaa"},
                {"source": "doc.txt", "chunk_index": 1, "chunk_id": "doc.txt:1:bbb"},
            ],
        }
        self.kb.vector_store.get.return_value = mock_result

        self.kb.ingestion._ensure_loaded()

        self.assertTrue(self.kb.ingestion._loaded)
        self.assertEqual(len(self.kb.all_docs), 2)
        self.assertEqual(len(self.kb.doc_by_id), 2)
        self.assertIsNotNone(self.kb.ingestion._bm25_index[0])


if __name__ == "__main__":
    unittest.main()
