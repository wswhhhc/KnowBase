"""Public/UI-safe settings helpers."""

from __future__ import annotations

from src.config import settings as settings_module

MASKED_SECRET_VALUE = settings_module.MASKED_SECRET_VALUE
_SECRET_SETTINGS = settings_module._SECRET_SETTINGS
get_public_settings = settings_module.get_public_settings
