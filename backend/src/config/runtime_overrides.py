"""Runtime override accessors for KnowBase settings."""

from __future__ import annotations

from src.config import settings as settings_module

get_runtime_setting = settings_module.get_runtime_setting
update_runtime_settings = settings_module.update_runtime_settings
get_all_settings = settings_module.get_all_settings
_RUNTIME_SETTINGS_PATH = settings_module._RUNTIME_SETTINGS_PATH
_runtime_overrides = settings_module._runtime_overrides
