import unittest

from langchain_core.documents import Document

from src.knowledge_base import KnowledgeBase, _document_chunk_id, rrf_fuse


class KnowledgeBaseTests(unittest.TestCase):
    def test_documents_from_chroma_result_restores_content_and_metadata(self):
        result = {
            "documents": ["hello", "", "world"],
            "metadatas": [{"source": "a.txt"}, {"source": "skip.txt"}, None],
        }

        docs = KnowledgeBase._documents_from_chroma_result(result)

        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].page_content, "hello")
        self.assertEqual(docs[0].metadata["source"], "a.txt")
        self.assertEqual(docs[0].metadata["chunk_index"], 0)
        self.assertTrue(docs[0].metadata["chunk_id"].startswith("a.txt:0:"))
        self.assertEqual(docs[1].page_content, "world")
        self.assertEqual(docs[1].metadata["source"], "unknown")

    def test_documents_from_legacy_chroma_ids_backfills_stable_chunk_id(self):
        result = {
            "ids": ["2c7f7c9f-legacy-uuid"],
            "documents": ["hello"],
            "metadatas": [{"source": "a.txt"}],
        }

        docs = KnowledgeBase._documents_from_chroma_result(result)

        self.assertTrue(docs[0].metadata["chunk_id"].startswith("a.txt:0:"))
        self.assertEqual(docs[0].metadata["legacy_chroma_id"], "2c7f7c9f-legacy-uuid")

    def test_prepare_splits_adds_stable_chunk_metadata(self):
        docs = [Document(page_content="同一段测试内容", metadata={"source": "a.txt"})]

        splits = KnowledgeBase._prepare_splits(docs)

        self.assertEqual(len(splits), 1)
        metadata = splits[0].metadata
        self.assertEqual(metadata["source"], "a.txt")
        self.assertEqual(metadata["chunk_index"], 0)
        self.assertIn("content_hash", metadata)
        self.assertIn("chunk_id", metadata)

    def test_same_content_from_different_sources_gets_distinct_chunk_ids(self):
        docs = [
            Document(page_content="同一段测试内容", metadata={"source": "a.txt"}),
            Document(page_content="同一段测试内容", metadata={"source": "b.txt"}),
        ]

        splits = KnowledgeBase._prepare_splits(docs)

        self.assertEqual(splits[0].metadata["content_hash"], splits[1].metadata["content_hash"])
        self.assertNotEqual(splits[0].metadata["chunk_id"], splits[1].metadata["chunk_id"])

    def test_document_chunk_id_backfills_legacy_metadata(self):
        doc = Document(page_content="legacy", metadata={"source": "old.txt", "chunk_index": 2})

        chunk_id = _document_chunk_id(doc)

        self.assertTrue(chunk_id.startswith("old.txt:2:"))
        self.assertEqual(doc.metadata["chunk_id"], chunk_id)

    def test_rrf_fuse_combines_ranked_sources_without_content_keys(self):
        fused = rrf_fuse(
            vector_ranked=[("chunk-a", 0.1), ("chunk-b", 0.2)],
            bm25_ranked=[("chunk-b", 4.0), ("chunk-c", 3.0)],
            limit=3,
        )

        self.assertEqual([item.chunk_id for item in fused], ["chunk-b", "chunk-a", "chunk-c"])
        self.assertGreater(fused[0].score, fused[1].score)


if __name__ == "__main__":
    unittest.main()
