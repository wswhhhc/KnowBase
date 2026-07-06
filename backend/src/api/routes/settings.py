"""Settings — runtime configuration read/write via API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_knowledge_base, require_admin_or_legacy_api_key
from src.api.models import RuntimeSettingsOut, RuntimeSettingsUpdate, SettingsUpdateResult
from src.config.public_settings import (
    MASKED_SECRET_VALUE,
    _SECRET_SETTINGS,
    get_public_settings,
)
from src.config.runtime_overrides import (
    update_runtime_settings,
)
from src.persistence import audit_store

router = APIRouter(dependencies=[Depends(require_admin_or_legacy_api_key)])


@router.get("")
async def get_settings() -> RuntimeSettingsOut:
    """Return all user-facing configuration settings."""
    return RuntimeSettingsOut.model_validate(get_public_settings())


@router.put("")
async def update_settings(
    body: RuntimeSettingsUpdate,
    current_user: dict | None = Depends(require_admin_or_legacy_api_key),
) -> SettingsUpdateResult:
    """Update runtime configuration. Only known keys are accepted."""
    filtered = body.model_dump(exclude_unset=True)
    filtered = {
        key: value
        for key, value in filtered.items()
        if not (key in _SECRET_SETTINGS and value == MASKED_SECRET_VALUE)
    }
    if not filtered:
        return SettingsUpdateResult(updated=False, message="没有有效的配置项")
    try:
        update_runtime_settings(filtered)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Detect embedding model change — requires re-indexing
    warnings = []
    if "embedding_model" in filtered:
        warnings.append("更换 embedding 模型后，需要清空并重新导入文档后才能继续检索")
    if {"chunk_size", "chunk_overlap", "enable_contextual_retrieval"} & set(filtered):
        warnings.append("切分相关配置只会影响后续新导入的文档，不会重写现有向量数据")

    if {"embedding_model", "siliconflow_base_url", "siliconflow_api_key"} & set(filtered):
        get_knowledge_base.cache_clear()

    changed_fields = sorted(filtered)
    secret_fields = sorted(key for key in filtered if key in _SECRET_SETTINGS)
    non_secret_values = {
        key: value
        for key, value in filtered.items()
        if key not in _SECRET_SETTINGS
    }
    audit_store.record_event(
        action="admin.settings_updated",
        actor_user_id=current_user.get("id") if current_user else None,
        target_type="settings",
        target_id="runtime",
        metadata={
            "changed_fields": changed_fields,
            "secret_fields": secret_fields,
            "non_secret_values": non_secret_values,
        },
    )

    return SettingsUpdateResult(updated=True, warnings=warnings)
