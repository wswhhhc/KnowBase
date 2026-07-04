"""Public/UI-safe runtime settings helpers."""

from __future__ import annotations

from src.config.runtime_overrides import get_runtime_setting

MASKED_SECRET_VALUE = "__KEEP_EXISTING_SECRET__"

_USER_FACING_SETTINGS = [
    "siliconflow_api_key", "siliconflow_base_url",
    "embedding_model", "llm_model", "llm_temperature",
    "tavily_api_key", "api_key",
    "chunk_size", "chunk_overlap", "top_k_retrieval", "top_k_rerank",
    "enable_quality_check", "enable_contextual_retrieval",
]
_SECRET_SETTINGS = {"siliconflow_api_key", "tavily_api_key", "api_key"}


def get_all_settings() -> dict:
    """Return all user-facing config (env defaults merged with runtime overrides)."""
    return {key: get_runtime_setting(key) for key in _USER_FACING_SETTINGS}


def get_public_settings() -> dict:
    """Return UI-safe settings, masking secrets instead of exposing raw values."""
    data = get_all_settings()
    for key in _SECRET_SETTINGS:
        value = str(data.get(key, "") or "")
        data[key] = MASKED_SECRET_VALUE if value else ""
    return data
