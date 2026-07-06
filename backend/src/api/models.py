"""Pydantic models for API request/response."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.rag.models import HotspotEntry, KBChunk


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4096)
    thread_id: str | None = None
    web_search_enabled: bool = False
    search_strategy: str = "balanced"
    pinned_chunk_ids: list[str] = Field(default_factory=list)
    excluded_chunk_ids: list[str] = Field(default_factory=list)
    workspace_id: str = ""


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class AuthSessionOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=256)
    role: str = Field(default="viewer", pattern="^(admin|editor|viewer)$")
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=256)
    role: str | None = Field(default=None, pattern="^(admin|editor|viewer)$")
    is_active: bool | None = None


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: str | None = None
    action: str
    target_type: str = ""
    target_id: str = ""
    metadata: dict = Field(default_factory=dict)
    created_at: str


class WorkspaceMemberIn(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field(..., pattern="^(admin|editor|viewer)$")


class WorkspaceMembersUpdate(BaseModel):
    members: list[WorkspaceMemberIn] = Field(default_factory=list)


class WorkspaceMemberOut(BaseModel):
    id: int
    workspace_id: str
    user_id: str
    username: str
    role: str
    created_at: str


class JobProgress(BaseModel):
    phase: str = ""
    percent: int = Field(default=0, ge=0, le=100)
    message: str = ""


class JobOut(BaseModel):
    id: str
    job_type: str
    status: str = Field(..., pattern="^(queued|running|succeeded|failed|canceled)$")
    created_by_user_id: str | None = None
    workspace_id: str = ""
    progress: JobProgress = Field(default_factory=JobProgress)
    error: str = ""
    attempts: int = 0
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None


class JobCreateResponse(BaseModel):
    job_id: str
    job: JobOut


class ChatSource(BaseModel):
    source: str
    chunk_id: str | None = None
    chunk_index: int | None = None
    page: int | None = None
    score: float | None = None
    content: str
    url: str | None = None
    index: int | None = None

    @field_validator("chunk_index", "page", "score", mode="before")
    @classmethod
    def _coerce_empty_numeric_fields(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ConversationCreate(BaseModel):
    title: str = "新对话"


class ConversationOut(BaseModel):
    id: str
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    last_message_preview: str = ""


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
    model_config = ConfigDict(populate_by_name=True)

    markdown: str = ""
    export_json: dict = Field(default_factory=dict, alias="json", serialization_alias="json")


class IngestResponse(BaseModel):
    chunk_count: int
    total_docs: int
    message: str
    suggested_questions: list[str] = Field(default_factory=list)
    existing_version: bool = False


class DemoImportResponse(BaseModel):
    chunk_count: int
    total_docs: int
    message: str
    imported_sources: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


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
    token_count: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    llm_model: str | None = None
    estimated_cost: float | None = None


class QueryLogsResponse(BaseModel):
    logs: list[QueryLogEntry] = Field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0


class RuntimeSettingsOut(BaseModel):
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"
    llm_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    llm_temperature: float = 0.3
    tavily_api_key: str = ""
    api_key: str = ""
    chunk_size: int = 1500
    chunk_overlap: int = 50
    top_k_retrieval: int = 5
    top_k_rerank: int = 3
    enable_quality_check: bool = True
    enable_contextual_retrieval: bool = True


class RuntimeSettingsUpdate(BaseModel):
    siliconflow_api_key: str | None = None
    siliconflow_base_url: str | None = None
    embedding_model: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = None
    tavily_api_key: str | None = None
    api_key: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    top_k_retrieval: int | None = None
    top_k_rerank: int | None = None
    enable_quality_check: bool | None = None
    enable_contextual_retrieval: bool | None = None


class SettingsUpdateResult(BaseModel):
    updated: bool
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


class PinStateOut(BaseModel):
    thread_id: str
    pinned_chunk_ids: list[str] = Field(default_factory=list)
    excluded_chunk_ids: list[str] = Field(default_factory=list)


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
    context_sources: list[ChatSource] = Field(default_factory=list)
    token_count: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class SourceOut(BaseModel):
    """Document source summary returned by GET /api/documents/sources."""

    source: str
    count: int


class KBConfig(BaseModel):
    """Knowledge base configuration returned by GET /api/knowledge-base/config."""

    chunk_size: int
    chunk_overlap: int
