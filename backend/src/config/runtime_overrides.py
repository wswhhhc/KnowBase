"""Runtime override storage and merged runtime config accessors for KnowBase settings."""

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


def _is_configured_api_key(api_key: str) -> bool:
    """Return whether the key looks like a real configured secret."""
    return bool(api_key) and api_key != "你的 API Key" and len(api_key.strip()) >= 10


def require_siliconflow_api_key() -> str:
    """Return a configured API key or raise a user-actionable error."""
    api_key = get_runtime_setting("siliconflow_api_key", settings.llm.api_key)
    if not _is_configured_api_key(api_key):
        raise ValueError(
            "缺少硅基流动 API Key。请在 .env 中配置 SILICONFLOW_API_KEY=你的密钥，"
            "或设置系统环境变量 SILICONFLOW_API_KEY。"
        )
    return api_key


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
