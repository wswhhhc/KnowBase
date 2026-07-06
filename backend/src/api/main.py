"""KnowBase API — FastAPI 主入口"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.rate_limit import RedisRateLimiter
from src.api.routes import admin_audit_logs, admin_users, auth, chat, conversations, documents, jobs, knowledge_base, metrics, workspaces, bookmarks, settings as settings_router
from src.api.deps import get_knowledge_base
from src.config.runtime_overrides import _is_configured_api_key, get_runtime_setting
from src.config.security import validate_production_security
from src.config.settings import settings
from src.persistence.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_production_security()
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
app.state.rate_limiter = RedisRateLimiter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_users.router, prefix="/api/admin", tags=["admin"])
app.include_router(admin_audit_logs.router, prefix="/api/admin", tags=["admin"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(knowledge_base.router, prefix="/api/knowledge-base", tags=["knowledge-base"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(bookmarks.router, prefix="/api/bookmarks", tags=["bookmarks"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
