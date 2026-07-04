"""Runtime override storage and accessors for KnowBase settings."""

from __future__ import annotations

import json

from src.config.settings import LOCAL_RUNTIME_DIR, Settings, settings

_RUNTIME_SETTINGS_PATH = LOCAL_RUNTIME_DIR / "runtime_settings.json"
_runtime_overrides: dict[str, str | float | bool | int] = {}
_MISSING = object()


def _load_runtime_settings() -> None:
    global _runtime_overrides
    try:
        if _RUNTIME_SETTINGS_PATH.exists():
            with open(_RUNTIME_SETTINGS_PATH, encoding="utf-8") as file:
                _runtime_overrides = json.load(file)
    except Exception:
        _runtime_overrides = {}


def get_runtime_setting(key: str, default=_MISSING):
    """Return the runtime-overridden value, or fall back to typed settings."""
    if key in _runtime_overrides:
        return _runtime_overrides[key]
    if default is _MISSING:
        return getattr(settings, key, None)
    return getattr(settings, key, default)


def update_runtime_settings(values: dict) -> None:
    """Validate and persist runtime config overrides to JSON."""
    global _runtime_overrides
    merged = settings.model_dump()
    merged.update(_runtime_overrides)
    merged.update(values)
    validated = Settings.model_validate(merged)
    normalized = {key: getattr(validated, key) for key in values}
    _runtime_overrides.update(normalized)
    _RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_RUNTIME_SETTINGS_PATH, "w", encoding="utf-8") as file:
        json.dump(_runtime_overrides, file, ensure_ascii=False, indent=2)


_load_runtime_settings()
