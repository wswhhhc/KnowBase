"""Pydantic models for API request/response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4096)
    thread_id: str | None = None
    web_search_enabled: bool = False
    search_strategy: str = "balanced"


class ChatSource(BaseModel):
    source: str
    chunk_index: int | None = None
    page: int | None = None
    score: float | None = None
    content: str
    url: str | None = None


class ConversationCreate(BaseModel):
    title: str = "新对话"


class ConversationOut(BaseModel):
    id: str
    thread_id: str
    title: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list[ChatSource] = []
    quality_reason: str = ""
    feedback: str | None = None
    created_at: str


class MessageFeedback(BaseModel):
    feedback: str


class ExportOut(BaseModel):
    markdown: str


class IngestResponse(BaseModel):
    chunk_count: int
    total_docs: int
    message: str


class URLIngestRequest(BaseModel):
    url: str = Field(..., description="Public URL to fetch and ingest")


class KBStats(BaseModel):
    chunk_count: int
    source_count: int
    total_chars: int


class KBChunk(BaseModel):
    source: str
    chunk_index: int
    chunk_id: str
    page: int | None = None
    content: str
    original_content: str | None = None
    section: str | None = None


class QueryLogEntry(BaseModel):
    timestamp: str
    question: str
    elapsed_ms: int
    retrieval_count: int
    quality_ok: bool
    quality_reason: str
    used_web_search: bool | None = None
    used_rerank: bool | None = None
    question_type: str = ""
    retry_count: int = 0
    source_count: int = 0
    answer_preview: str = ""
    error: str = ""
