"""Settings — runtime configuration read/write via API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import verify_api_key, get_knowledge_base
from src.api.models import RuntimeSettingsOut, RuntimeSettingsUpdate, SettingsUpdateResult
from src.config.settings import (
    MASKED_SECRET_VALUE,
    _SECRET_SETTINGS,
    get_public_settings,
    update_runtime_settings,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("")
async def get_settings() -> RuntimeSettingsOut:
    """Return all user-facing configuration settings."""
    return RuntimeSettingsOut.model_validate(get_public_settings())


@router.put("")
async def update_settings(body: RuntimeSettingsUpdate) -> SettingsUpdateResult:
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

    return SettingsUpdateResult(updated=True, warnings=warnings)
