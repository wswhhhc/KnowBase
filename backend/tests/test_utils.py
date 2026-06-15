import unittest

from src.utils import extract_context_terms, sanitize_upload_filename, validate_upload


class FakeUpload:
    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size


class UploadUtilityTests(unittest.TestCase):
    def test_sanitize_upload_filename_removes_path_segments(self):
        self.assertEqual(sanitize_upload_filename("..\\secret/合同.md"), "合同.md")

    def test_sanitize_upload_filename_rejects_empty_names(self):
        with self.assertRaises(ValueError):
            sanitize_upload_filename("../")

    def test_validate_upload_rejects_large_files(self):
        upload = FakeUpload("notes.txt", size=4 * 1024 * 1024)

        with self.assertRaises(ValueError):
            validate_upload(upload, max_upload_mb=3)

    def test_validate_upload_rejects_unsupported_extensions(self):
        upload = FakeUpload("notes.xyz", size=1024)

        with self.assertRaises(ValueError):
            validate_upload(upload, max_upload_mb=3)

    def test_validate_upload_accepts_new_formats(self):
        for ext in [".txt", ".md", ".pdf", ".docx", ".html", ".htm"]:
            upload = FakeUpload(f"notes{ext}", size=1024)
            try:
                validate_upload(upload, max_upload_mb=3)
            except ValueError:
                self.fail(f"validate_upload rejected valid extension: {ext}")


class ExtractContextTermsTests(unittest.TestCase):
    def test_extract_from_simple_sentence(self):
        terms = extract_context_terms("ChatGPT 各版本定价方案对比", top_n=3)
        for term in ("chatgpt", "定价"):
            self.assertIn(term, terms)

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(extract_context_terms(""), [])
        self.assertEqual(extract_context_terms("   "), [])

    def test_stop_words_only_returns_empty(self):
        self.assertEqual(extract_context_terms("的 了 是 在 有"), [])

    def test_top_n_respected(self):
        terms = extract_context_terms("苹果 香蕉 苹果 香蕉 橘子", top_n=2)
        self.assertEqual(len(terms), 2)

    def test_stop_words_filtered_from_results(self):
        terms = extract_context_terms("这是一个测试文档", top_n=5)
        self.assertNotIn("的", terms)
        self.assertNotIn("一个", terms)
        self.assertIn("测试", terms)

    def test_repeated_terms_ranked_higher(self):
        terms = extract_context_terms("文档 文档 测试 测试 测试 代码", top_n=2)
        self.assertEqual(terms[0], "测试")
        self.assertEqual(terms[1], "文档")


if __name__ == "__main__":
    unittest.main()
