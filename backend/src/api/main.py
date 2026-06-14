"""KnowBase API — FastAPI 主入口"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, conversations, documents, knowledge_base, metrics
from src.api.deps import get_knowledge_base
from src.conversations import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    get_knowledge_base()
    yield


app = FastAPI(title="KnowBase API", version="0.1.0", lifespan=lifespan)

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
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
