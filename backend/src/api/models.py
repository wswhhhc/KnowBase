"""Pydantic models for API request/response."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4096)
    thread_id: str | None = None
    web_search_enabled: bool = False
    search_strategy: str = "balanced"
    pinned_chunk_ids: list[str] = Field(default_factory=list)
    excluded_chunk_ids: list[str] = Field(default_factory=list)
    workspace_id: str = ""


class ChatSource(BaseModel):
    source: str
    chunk_id: str | None = None
    chunk_index: int | None = None
    page: int | None = None
    score: float | None = None
    content: str
    url: str | None = None
    index: int | None = None


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
    sources: list[ChatSource] = Field(default_factory=list)
    quality_reason: str = ""
    debug_info: dict = Field(default_factory=dict)
    feedback: str | None = None
    created_at: str


class MessageFeedback(BaseModel):
    feedback: str
    category: str | None = None
    detail: str | None = None


class ExportOut(BaseModel):
    markdown: str = ""
    json: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    chunk_count: int
    total_docs: int
    message: str
    suggested_questions: list[str] = Field(default_factory=list)
    existing_version: bool = False


class URLIngestRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Public URL to fetch and ingest")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("url must be a valid HTTP/HTTPS URL")
        return value


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
    thread_id: str = ""
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
    ttfb_ms: int = 0
    first_token_ms: int = 0


class NodeDebug(BaseModel):
    """一个图节点的执行调试信息。"""

    name: str
    label: str
    elapsed_ms: int = 0
    summary: str = ""


class DebugInfo(BaseModel):
    """整条消息的调试信息，通过 SSE debug 事件下发。"""

    nodes: list[NodeDebug] = Field(default_factory=list)
    rewritten_question: str = ""
    retrieval_k: int = 0
    candidates_before: int = 0
    candidates_after: int = 0
    after_rerank: int = 0
    used_rerank: bool = False
    used_rewrite: bool = False
    quality_passed: bool = True
    quality_reason: str = ""
    retry_count: int = 0
    used_web_search: bool = False
    web_results_count: int = 0


class SourceOut(BaseModel):
    """Document source summary returned by GET /api/documents/sources."""

    source: str
    count: int


class HotspotEntry(BaseModel):
    """Hot chunk entry returned by GET /api/knowledge-base/hotspots."""

    chunk_id: str
    source: str
    hits: int
    content_preview: str


class KBConfig(BaseModel):
    """Knowledge base configuration returned by GET /api/knowledge-base/config."""

    chunk_size: int
    chunk_overlap: int
