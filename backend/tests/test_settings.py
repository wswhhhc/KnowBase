import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import src.config.settings as settings_module
import src.config.runtime_overrides as runtime_overrides_module
from src.api import deps as api_deps
from src.config.settings import Settings
from src.api import main as api_main
from src.config.security import validate_production_security


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.original_runtime_overrides = dict(runtime_overrides_module._runtime_overrides)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self.temp_dir.name) / "runtime_settings.json"
        self.path_patcher = patch.object(runtime_overrides_module, "_RUNTIME_SETTINGS_PATH", self.runtime_path)
        self.path_patcher.start()
        runtime_overrides_module._runtime_overrides = {}

    def tearDown(self):
        self.path_patcher.stop()
        runtime_overrides_module._runtime_overrides = self.original_runtime_overrides
        self.temp_dir.cleanup()

    def test_is_configured_api_key_rejects_placeholders_and_short_values(self):
        self.assertFalse(runtime_overrides_module._is_configured_api_key(""))
        self.assertFalse(runtime_overrides_module._is_configured_api_key("你的 API Key"))
        self.assertFalse(runtime_overrides_module._is_configured_api_key("abc123"))
        self.assertFalse(runtime_overrides_module._is_configured_api_key("sk-runtime-1234567890"))
        self.assertTrue(runtime_overrides_module._is_configured_api_key("sk-1234567890"))

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

    def test_settings_exposes_layered_views(self):
        settings = Settings(
            SILICONFLOW_API_KEY="sk-1234567890",
            SILICONFLOW_BASE_URL="https://example.com/v1",
            EMBEDDING_MODEL="demo-embed",
            LLM_MODEL="demo-llm",
            TOP_K_RETRIEVAL="9",
            ENABLE_QUALITY_CHECK="false",
            API_KEY="local-key",
        )

        self.assertEqual(settings.llm.api_key, "sk-1234567890")
        self.assertEqual(settings.llm.base_url, "https://example.com/v1")
        self.assertEqual(settings.llm.model, "demo-llm")
        self.assertEqual(settings.retrieval.top_k, 9)
        self.assertFalse(settings.quality.enabled)
        self.assertEqual(settings.auth.api_key, "local-key")

    def test_settings_parses_cors_allow_origins(self):
        settings = Settings(
            SILICONFLOW_API_KEY="sk-1234567890",
            CORS_ALLOW_ORIGINS="https://knowbase.internal, http://localhost:5173,",
        )

        self.assertEqual(
            settings.api.cors_allow_origins,
            ["https://knowbase.internal", "http://localhost:5173"],
        )

    def test_settings_defaults_cors_to_local_development_origins(self):
        settings = Settings(SILICONFLOW_API_KEY="sk-1234567890")

        self.assertEqual(
            settings.api.cors_allow_origins,
            ["http://localhost:5173", "http://localhost:3000"],
        )

    def test_settings_identifies_production_environment(self):
        self.assertTrue(Settings(APP_ENV="production").is_production)
        self.assertTrue(Settings(APP_ENV="prod").is_production)
        self.assertFalse(Settings(APP_ENV="development").is_production)

    def test_validate_production_security_requires_hardened_settings(self):
        settings = Settings(
            APP_ENV="production",
            JWT_SECRET="short",
            DATABASE_URL="sqlite:///runtime/local/conversations.db",
            CORS_ALLOW_ORIGINS="http://localhost:5173,*",
            API_KEY="legacy-key",
            KNOWBASE_E2E_FAKE_AI="true",
        )

        with pytest.raises(RuntimeError) as exc:
            validate_production_security(settings)

        message = str(exc.value)
        self.assertIn("JWT_SECRET", message)
        self.assertIn("DATABASE_URL", message)
        self.assertIn("CORS_ALLOW_ORIGINS", message)
        self.assertIn("API_KEY", message)
        self.assertIn("KNOWBASE_E2E_FAKE_AI", message)

    def test_validate_production_security_accepts_hardened_settings(self):
        settings = Settings(
            APP_ENV="production",
            JWT_SECRET="x" * 48,
            DATABASE_URL="postgresql+psycopg://knowbase:pw@postgres/knowbase",
            CORS_ALLOW_ORIGINS="https://knowbase.internal",
        )

        validate_production_security(settings)

    def test_production_rejects_legacy_api_key_path(self):
        production_settings = Settings(
            APP_ENV="production",
            JWT_SECRET="x" * 48,
            API_KEY="legacy-key",
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="legacy-key")

        with patch.object(api_deps, "settings", production_settings):
            with patch.object(api_deps, "get_runtime_setting", return_value="legacy-key"):
                with self.assertRaises(HTTPException) as ctx:
                    api_deps.get_current_user_or_legacy_api_key(credentials)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_production_rejects_anonymous_local_dev_path(self):
        production_settings = Settings(APP_ENV="production", JWT_SECRET="x" * 48)

        with patch.object(api_deps, "settings", production_settings):
            with patch.object(api_deps, "get_runtime_setting", return_value=""):
                with self.assertRaises(HTTPException) as ctx:
                    api_deps.get_current_user_or_legacy_api_key(None)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_settings_defaults_runtime_paths_to_runtime_local(self):
        settings = Settings(SILICONFLOW_API_KEY="sk-1234567890")
        repo_root = Path(__file__).resolve().parents[2]

        self.assertEqual(settings_module.ROOT_DIR, repo_root)
        self.assertEqual(settings_module.BACKEND_DIR, repo_root / "backend")
        self.assertEqual(settings_module.EXAMPLES_DIR, repo_root / "examples")
        self.assertEqual(settings_module.LOCAL_RUNTIME_DIR, repo_root / "runtime" / "local")
        self.assertEqual(settings_module.QUICKSTART_RUNTIME_DIR, repo_root / "runtime" / "quickstart")
        self.assertEqual(settings.chroma_persist_dir, repo_root / "runtime" / "local" / "chroma_db")
        self.assertEqual(settings.data_dir, repo_root / "runtime" / "local")
        self.assertEqual(settings.checkpoint_db_path, str(repo_root / "runtime" / "local" / "checkpoints.db"))

    def test_settings_resolve_relative_storage_paths_from_repository_root(self):
        repo_root = Path(__file__).resolve().parents[2]
        settings = Settings(
            SILICONFLOW_API_KEY="sk-1234567890",
            CHROMA_PERSIST_DIR="runtime/custom/chroma",
            DATA_DIR="runtime/custom/data",
            CHECKPOINT_DB_PATH="runtime/custom/checkpoints.db",
        )

        self.assertEqual(settings.chroma_persist_dir, repo_root / "runtime" / "custom" / "chroma")
        self.assertEqual(settings.data_dir, repo_root / "runtime" / "custom" / "data")
        self.assertEqual(settings.checkpoint_db_path, str(repo_root / "runtime" / "custom" / "checkpoints.db"))

    def test_update_runtime_settings_coerces_types(self):
        runtime_overrides_module.update_runtime_settings({
            "llm_temperature": "0.7",
            "top_k_retrieval": "8",
            "enable_quality_check": False,
        })

        self.assertEqual(runtime_overrides_module.get_runtime_setting("llm_temperature"), 0.7)
        self.assertEqual(runtime_overrides_module.get_runtime_setting("top_k_retrieval"), 8)
        self.assertFalse(runtime_overrides_module.get_runtime_setting("enable_quality_check"))

    def test_require_siliconflow_api_key_prefers_runtime_override(self):
        runtime_overrides_module.update_runtime_settings({"siliconflow_api_key": "sk-live-1234567890"})

        self.assertEqual(
            runtime_overrides_module.require_siliconflow_api_key(),
            "sk-live-1234567890",
        )

    def test_require_siliconflow_api_key_ignores_invalid_runtime_override(self):
        runtime_overrides_module._runtime_overrides = {"siliconflow_api_key": "sk-runtime-1234567890"}
        fallback_settings = Settings(SILICONFLOW_API_KEY="sk-env-1234567890")

        with patch.object(runtime_overrides_module, "settings", fallback_settings):
            self.assertEqual(
                runtime_overrides_module.require_siliconflow_api_key(),
                "sk-env-1234567890",
            )

    def test_update_runtime_settings_rejects_invalid_siliconflow_override(self):
        with self.assertRaisesRegex(ValueError, "SILICONFLOW_API_KEY 看起来无效"):
            runtime_overrides_module.update_runtime_settings({
                "siliconflow_api_key": "sk-runtime-1234567890",
            })

    def test_update_runtime_settings_blank_siliconflow_override_falls_back_to_env(self):
        runtime_overrides_module._runtime_overrides = {"siliconflow_api_key": "sk-live-1234567890"}
        runtime_overrides_module.update_runtime_settings({"siliconflow_api_key": ""})

        self.assertNotIn("siliconflow_api_key", runtime_overrides_module._runtime_overrides)
        with open(self.runtime_path, encoding="utf-8") as file:
            self.assertNotIn("siliconflow_api_key", file.read())

    def test_lifespan_uses_runtime_api_key_override_for_preset_loading(self):
        fake_kb = MagicMock()

        with patch.object(api_main, "get_runtime_setting", return_value="sk-live-1234567890"):
            with patch.object(api_main, "_is_configured_api_key", return_value=True):
                with patch.object(api_main, "init_db") as mock_init_db:
                    with patch.object(api_main, "get_knowledge_base", return_value=fake_kb):
                        async def _run():
                            async with api_main.lifespan(api_main.app):
                                return None

                        asyncio.run(_run())

        mock_init_db.assert_called_once()
        fake_kb.load_preset_documents.assert_called_once()


if __name__ == "__main__":
    unittest.main()
