"""Runtime override storage and merged runtime config accessors for KnowBase settings."""

from __future__ import annotations

import json

from src.config.settings import LOCAL_RUNTIME_DIR, Settings, settings

_RUNTIME_SETTINGS_PATH = LOCAL_RUNTIME_DIR / "runtime_settings.json"
_runtime_overrides: dict[str, str | float | bool | int] = {}
_MISSING = object()
_API_KEY_PLACEHOLDERS = {
    "你的 api key",
    "你的 key",
    "your api key",
    "your key",
    "your_api_key",
    "api-key-here",
}
_API_KEY_INVALID_PREFIXES = (
    "sk-runtime-",
    "sk-test-",
    "sk-demo-",
    "sk-placeholder-",
    "sk-fake-",
    "sk-invalid-",
)


def _sanitize_runtime_overrides(values: dict[str, str | float | bool | int]) -> dict[str, str | float | bool | int]:
    sanitized = dict(values)
    candidate = sanitized.get("siliconflow_api_key")
    if isinstance(candidate, str) and candidate.strip() and not _is_configured_api_key(candidate):
        sanitized.pop("siliconflow_api_key", None)
    return sanitized


def _load_runtime_settings() -> None:
    global _runtime_overrides
    try:
        if _RUNTIME_SETTINGS_PATH.exists():
            with open(_RUNTIME_SETTINGS_PATH, encoding="utf-8") as file:
                _runtime_overrides = _sanitize_runtime_overrides(json.load(file))
    except Exception:
        _runtime_overrides = {}


def get_runtime_setting(key: str, default=_MISSING):
    """Return the runtime-overridden value, or fall back to typed settings."""
    if key in _runtime_overrides:
        value = _runtime_overrides[key]
        if key == "siliconflow_api_key" and isinstance(value, str) and not _is_configured_api_key(value):
            pass
        else:
            return value
    if default is _MISSING:
        return getattr(settings, key, None)
    return getattr(settings, key, default)


def _is_configured_api_key(api_key: str) -> bool:
    """Return whether the key looks like a real configured secret."""
    normalized = api_key.strip().lower()
    if not normalized:
        return False
    if normalized == "你的 api key":
        return False
    if normalized in _API_KEY_PLACEHOLDERS:
        return False
    if len(normalized) < 10:
        return False
    return not normalized.startswith(_API_KEY_INVALID_PREFIXES)


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
    normalized_values = dict(values)
    if "siliconflow_api_key" in normalized_values:
        candidate = str(normalized_values["siliconflow_api_key"] or "").strip()
        if not candidate:
            normalized_values.pop("siliconflow_api_key", None)
            _runtime_overrides.pop("siliconflow_api_key", None)
        elif not _is_configured_api_key(candidate):
            raise ValueError(
                "SILICONFLOW_API_KEY 看起来无效。"
                "请填写真实的硅基流动密钥，或留空以回退到 .env / 系统环境变量。"
            )
        else:
            normalized_values["siliconflow_api_key"] = candidate

    if not normalized_values and values:
        _RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_RUNTIME_SETTINGS_PATH, "w", encoding="utf-8") as file:
            json.dump(_runtime_overrides, file, ensure_ascii=False, indent=2)
        return

    merged = settings.model_dump()
    merged.update(_runtime_overrides)
    merged.update(normalized_values)
    validated = Settings.model_validate(merged)
    normalized = {key: getattr(validated, key) for key in normalized_values}
    _runtime_overrides.update(normalized)
    _RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_RUNTIME_SETTINGS_PATH, "w", encoding="utf-8") as file:
        json.dump(_runtime_overrides, file, ensure_ascii=False, indent=2)


_load_runtime_settings()
