"""KnowBase API — FastAPI 主入口"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.rate_limit import InMemoryRateLimiter
from src.api.routes import chat, conversations, documents, knowledge_base, metrics, workspaces, bookmarks, settings as settings_router
from src.api.deps import get_knowledge_base
from src.config.runtime_overrides import get_runtime_setting
from src.config.settings import _is_configured_api_key, settings
from src.persistence.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    api_key = get_runtime_setting("siliconflow_api_key", settings.llm.api_key)
    if _is_configured_api_key(api_key):
        try:
            kb = get_knowledge_base()
            kb.load_preset_documents()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("预设文档加载失败（app 仍可正常启动）: %s", exc)
    yield


app = FastAPI(title="KnowBase API", version="0.1.0", lifespan=lifespan)
app.state.rate_limiter = InMemoryRateLimiter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(knowledge_base.router, prefix="/api/knowledge-base", tags=["knowledge-base"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(bookmarks.router, prefix="/api/bookmarks", tags=["bookmarks"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
