import unittest
from pathlib import Path
import tempfile

from src.loaders import load_document


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _write(self, name: str, content: str) -> str:
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_load_txt(self):
        path = self._write("test.txt", "你好世界")
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].page_content, "你好世界")
        self.assertEqual(docs[0].metadata["source"], "test.txt")

    def test_load_md(self):
        path = self._write("test.md", "# Title\n\nContent.")
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Content", docs[0].page_content)

    def test_load_pdf_returns_pages(self):
        """Create a minimal PDF and verify it produces page Documents."""
        from io import BytesIO
        from pypdf import PdfWriter

        # Write a minimal PDF with markdown metadata so we get extractable text.
        pdf_path = str(self.tmp / "test.pdf")
        writer = PdfWriter()
        writer.add_blank_page(72, 72)
        writer.add_metadata({"/Title": "Test Page"})
        writer.write(pdf_path)

        docs = load_document(pdf_path)
        self.assertGreaterEqual(len(docs), 1)
        for doc in docs:
            self.assertIn("page", doc.metadata)

    def test_load_docx(self):
        from docx import Document as DocxDocument

        docx_path = str(self.tmp / "test.docx")
        doc = DocxDocument()
        doc.add_paragraph("Hello from docx.")
        doc.save(docx_path)

        docs = load_document(docx_path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Hello from docx", docs[0].page_content)
        self.assertEqual(docs[0].metadata["source"], "test.docx")

    def test_load_html(self):
        path = self._write(
            "test.html",
            "<html><body><h1>Title</h1><p>Content.</p></body></html>",
        )
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Title", docs[0].page_content)
        self.assertIn("Content", docs[0].page_content)

    def test_load_html_strips_script_style(self):
        path = self._write(
            "test.html",
            "<html><body><script>alert(1)</script><style>.c{}</style><p>Real.</p></body></html>",
        )
        docs = load_document(path)
        self.assertNotIn("alert", docs[0].page_content)
        self.assertIn("Real", docs[0].page_content)

    def test_load_unsupported_extension_raises(self):
        with self.assertRaises(ValueError):
            load_document(str(self.tmp / "data.xyz"))

    def test_source_name_overrides_file_path_name(self):
        path = self._write("actual.txt", "data")
        docs = load_document(path, source_name="custom.txt")
        self.assertEqual(docs[0].metadata["source"], "custom.txt")

    def test_load_htm_as_html(self):
        path = self._write("page.htm", "<html><p>Hello</p></html>")
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Hello", docs[0].page_content)


if __name__ == "__main__":
    unittest.main()
