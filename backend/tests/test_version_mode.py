"""Tests for version_mode (replace/append/skip) in IngestionService."""

import unittest
from unittest.mock import patch, MagicMock

from langchain_core.documents import Document

from src.knowledge_base import IngestionService, KnowledgeBase
from src.kb_models import normalize_source


class VersionModeTests(unittest.TestCase):
    """Test replace/append/skip semantics in ingest_file."""

    def setUp(self):
        # Build a real KnowledgeBase (mocked Chroma) so we have real
        # all_docs / doc_by_id / existing_chunk_ids / BM25 state.
        with patch("src.knowledge_base.Chroma") as mock_chroma:
            with patch("src.knowledge_base.OpenAIEmbeddings"):
                with patch("src.knowledge_base.require_siliconflow_api_key", return_value="sk-test"):
                    self.kb = KnowledgeBase()

        # Populate with an initial document for "doc.txt" using same path as real ingest
        from src.loaders import load_document

        self.kb.ingestion._ensure_loaded = MagicMock()

    def _make_file_docs(self, content: str, source: str = "doc.txt") -> list[Document]:
        return [Document(page_content=content, metadata={"source": source, "chunk_id": f"{source}:0:test"})]

    def test_replace_removes_old_chunks(self):
        """With version_mode='replace', old chunks for the source are removed."""
        with patch("src.knowledge_base.load_document", return_value=self._make_file_docs("new content")):
            with patch.object(self.kb.ingestion, "_replace_old_chunks") as mock_replace:
                self.kb.ingestion.ingest_file("/f/doc.txt", source_name="doc.txt", version_mode="replace")
                mock_replace.assert_called_once()

    def test_append_keeps_old_chunks(self):
        """With version_mode='append', old chunks remain after ingest."""
        # Directly insert an "old" chunk into state
        self.kb.ingestion._all_docs.append(
            Document(page_content="old", metadata={"source": "doc.txt", "chunk_id": "doc.txt:0:old"})
        )
        self.kb.ingestion._doc_by_id["doc.txt:0:old"] = self.kb.ingestion._all_docs[-1]
        self.kb.ingestion._existing_chunk_ids.add("doc.txt:0:old")

        with patch("src.knowledge_base.load_document", return_value=self._make_file_docs("appended content")):
            with patch.object(self.kb.ingestion, "_replace_old_chunks") as mock_replace:
                self.kb.ingestion.ingest_file("/f/doc.txt", source_name="doc.txt", version_mode="append")
                mock_replace.assert_not_called()
        # Old chunk should still be present
        self.assertIn("doc.txt:0:old", self.kb.ingestion._existing_chunk_ids)

    def test_skip_when_source_exists_returns_zero(self):
        """With version_mode='skip', if source exists, no new chunks added and returns 0."""
        self.kb.ingestion._all_docs.append(
            Document(page_content="existing", metadata={"source": "doc.txt", "chunk_id": "doc.txt:0:exist"})
        )
        self.kb.ingestion._existing_chunk_ids.add("doc.txt:0:exist")
        before_count = len(self.kb.ingestion._all_docs)
        with patch("src.knowledge_base.load_document", return_value=self._make_file_docs("skipped content")):
            result = self.kb.ingestion.ingest_file("/f/doc.txt", source_name="doc.txt", version_mode="skip")
        self.assertEqual(result, 0)
        self.assertEqual(len(self.kb.ingestion._all_docs), before_count)

    def test_skip_when_source_absent_ingests_normally(self):
        """With version_mode='skip', if source does NOT exist, ingest normally."""
        before_count = len(self.kb.ingestion._all_docs)
        # Make _process_documents return 0 (no duplicates)
        new_doc = self._make_file_docs("fresh content", source="new_doc.txt")
        with patch("src.knowledge_base.load_document", return_value=new_doc):
            with patch.object(self.kb.ingestion, "_process_documents", return_value=1):
                result = self.kb.ingestion.ingest_file("/f/new_doc.txt", source_name="new_doc.txt", version_mode="skip")
        self.assertEqual(result, 1)

    def test_first_upload_without_version_mode_works(self):
        """Default version_mode='replace' on first upload does not break anything."""
        new_doc = self._make_file_docs("brand new", source="fresh.txt")
        with patch("src.knowledge_base.load_document", return_value=new_doc):
            result = self.kb.ingestion.ingest_file("/f/fresh.txt", source_name="fresh.txt")
        self.assertGreater(result, 0)


if __name__ == "__main__":
    unittest.main()
