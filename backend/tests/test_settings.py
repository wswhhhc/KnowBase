import unittest

from config.settings import Settings, _is_configured_api_key


class SettingsTests(unittest.TestCase):
    def test_is_configured_api_key_rejects_placeholders_and_short_values(self):
        self.assertFalse(_is_configured_api_key(""))
        self.assertFalse(_is_configured_api_key("你的 API Key"))
        self.assertFalse(_is_configured_api_key("abc123"))
        self.assertTrue(_is_configured_api_key("sk-1234567890"))

    def test_settings_reads_typed_env_values(self):
        settings = Settings(
            SILICONFLOW_API_KEY="sk-1234567890",
            TOP_K_RETRIEVAL="9",
            MAX_UPLOAD_MB="3",
            LANGSMITH_TRACING="true",
        )

        self.assertEqual(settings.siliconflow_api_key, "sk-1234567890")
        self.assertEqual(settings.top_k_retrieval, 9)
        self.assertEqual(settings.max_upload_mb, 3)
        self.assertTrue(settings.langsmith_tracing)


if __name__ == "__main__":
    unittest.main()
