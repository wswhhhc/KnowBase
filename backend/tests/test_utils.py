import unittest

from src.utils import sanitize_upload_filename, validate_upload


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


if __name__ == "__main__":
    unittest.main()
