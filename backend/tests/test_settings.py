import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from config import settings as settings_module
from config.settings import Settings, _is_configured_api_key
from src.api import main as api_main


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.original_runtime_overrides = dict(settings_module._runtime_overrides)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self.temp_dir.name) / "runtime_settings.json"
        self.path_patcher = patch.object(settings_module, "_RUNTIME_SETTINGS_PATH", self.runtime_path)
        self.path_patcher.start()
        settings_module._runtime_overrides = {}

    def tearDown(self):
        self.path_patcher.stop()
        settings_module._runtime_overrides = self.original_runtime_overrides
        self.temp_dir.cleanup()

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

    def test_update_runtime_settings_coerces_types(self):
        settings_module.update_runtime_settings({
            "llm_temperature": "0.7",
            "top_k_retrieval": "8",
            "enable_quality_check": False,
        })

        self.assertEqual(settings_module.get_runtime_setting("llm_temperature"), 0.7)
        self.assertEqual(settings_module.get_runtime_setting("top_k_retrieval"), 8)
        self.assertFalse(settings_module.get_runtime_setting("enable_quality_check"))

    def test_require_siliconflow_api_key_prefers_runtime_override(self):
        settings_module.update_runtime_settings({"siliconflow_api_key": "sk-runtime-1234567890"})

        self.assertEqual(
            settings_module.require_siliconflow_api_key(),
            "sk-runtime-1234567890",
        )

    def test_lifespan_uses_runtime_api_key_override_for_preset_loading(self):
        fake_kb = MagicMock()

        with patch.object(api_main, "get_runtime_setting", return_value="sk-runtime-1234567890"):
            with patch.object(api_main, "_is_configured_api_key", return_value=True):
                with patch.object(api_main, "get_knowledge_base", return_value=fake_kb):
                    async def _run():
                        async with api_main.lifespan(api_main.app):
                            return None

                    asyncio.run(_run())

        fake_kb.load_preset_documents.assert_called_once()


if __name__ == "__main__":
    unittest.main()
