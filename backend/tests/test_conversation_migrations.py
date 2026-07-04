import runpy
import sys
import tempfile
import types
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests import conversation_store as conversations
from src.config import settings as settings_module
from src.persistence import database as database_module


class _FakeAlembicConfig:
    def __init__(self, options: dict[str, str]):
        self._options = dict(options)
        self.config_file_name = None
        self.config_ini_section = "alembic"

    def get_main_option(self, key: str) -> str:
        return self._options.get(key, "")

    def set_main_option(self, key: str, value: str) -> None:
        self._options[key] = value

    def get_section(self, _section: str, default: dict | None = None) -> dict:
        return default or {}


class ConversationMigrationTests(unittest.TestCase):
    def tearDown(self):
        database_module.clear_db_path_override()

    def test_run_migrations_uses_runtime_local_database_by_default(self):
        with patch("alembic.command.upgrade") as mock_upgrade:
            with patch("alembic.config.Config") as mock_config_cls:
                mock_config = MagicMock()
                mock_config_cls.return_value = mock_config

                conversations._run_migrations()

        mock_config.set_main_option.assert_called_once_with(
            "sqlalchemy.url",
            f"sqlite:///{settings_module.LOCAL_RUNTIME_DIR / 'conversations.db'}",
        )
        mock_upgrade.assert_called_once_with(mock_config, "head")

    def test_database_run_migrations_uses_runtime_local_database_by_default(self):
        with patch("alembic.command.upgrade") as mock_upgrade:
            with patch("alembic.config.Config") as mock_config_cls:
                mock_config = MagicMock()
                mock_config_cls.return_value = mock_config

                database_module.run_migrations()

        mock_config.set_main_option.assert_called_once_with(
            "sqlalchemy.url",
            f"sqlite:///{settings_module.LOCAL_RUNTIME_DIR / 'conversations.db'}",
        )
        mock_upgrade.assert_called_once_with(mock_config, "head")

    def test_database_run_migrations_skips_non_runtime_override_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_module.set_db_path_override(Path(temp_dir) / "conversations.db")
            with patch("alembic.command.upgrade") as mock_upgrade:
                with patch("alembic.config.Config") as mock_config_cls:
                    database_module.run_migrations()

        self.assertFalse(mock_config_cls.called)
        self.assertFalse(mock_upgrade.called)

    def test_conversations_run_migrations_clears_stale_override_for_default_runtime_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_module.set_db_path_override(Path(temp_dir) / "conversations.db")
            with patch("alembic.command.upgrade") as mock_upgrade:
                with patch("alembic.config.Config") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config_cls.return_value = mock_config

                    conversations._run_migrations()

        mock_config.set_main_option.assert_called_once_with(
            "sqlalchemy.url",
            f"sqlite:///{settings_module.LOCAL_RUNTIME_DIR / 'conversations.db'}",
        )
        mock_upgrade.assert_called_once_with(mock_config, "head")

    def test_conversations_init_db_syncs_database_override(self):
        original_db_path = conversations._DB_PATH
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_db_path = Path(temp_dir) / "conversations.db"
                conversations._DB_PATH = temp_db_path
                with patch.object(database_module, "init_db") as mock_init_db:
                    conversations.init_db()

                self.assertEqual(database_module.get_db_path(), temp_db_path)
                mock_init_db.assert_called_once()
        finally:
            conversations._DB_PATH = original_db_path
            database_module.clear_db_path_override()

    def test_alembic_env_preserves_preconfigured_database_url(self):
        configured_url = "sqlite:///custom-runtime/conversations.db"
        fake_config = _FakeAlembicConfig({"sqlalchemy.url": configured_url})
        fake_context = types.SimpleNamespace(
            config=fake_config,
            is_offline_mode=lambda: True,
            configure=MagicMock(),
            begin_transaction=lambda: nullcontext(),
            run_migrations=MagicMock(),
        )
        fake_alembic = types.ModuleType("alembic")
        fake_alembic.context = fake_context

        fake_sqlalchemy = types.ModuleType("sqlalchemy")
        fake_sqlalchemy.engine_from_config = MagicMock()
        fake_sqlalchemy.pool = types.SimpleNamespace(NullPool=object())

        with patch("logging.config.fileConfig"):
            with patch.dict(
                sys.modules,
                {
                    "alembic": fake_alembic,
                    "sqlalchemy": fake_sqlalchemy,
                },
            ):
                env_py = Path(__file__).resolve().parents[1] / "migrations" / "env.py"
                runpy.run_path(str(env_py))

        self.assertEqual(fake_config.get_main_option("sqlalchemy.url"), configured_url)


if __name__ == "__main__":
    unittest.main()
