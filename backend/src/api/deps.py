"""Dependency injection for FastAPI — shared KnowledgeBase lifecycle."""

from __future__ import annotations

from functools import lru_cache
from src.knowledge_base import KnowledgeBase
from config.settings import settings


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    kb = KnowledgeBase()
    if settings.siliconflow_api_key:
        kb.load_preset_documents()
    return kb
