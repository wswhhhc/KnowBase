"""Graph state, partial updates, and structured workflow models."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.kb_models import RetrievalResult


QuestionType = Literal["knowledge_base", "chat_memory", "conversation_summary", "clarification"]
RetryStrategy = Literal["none", "rewrite_query", "expand_retrieval", "insufficient_context", "web_search"]
SearchStrategy = Literal["fast", "balanced", "high_quality", "deep"]
EvidenceLevel = Literal["none", "weak", "moderate", "strong"]
OutcomeCategory = Literal["success", "no_docs", "web_empty", "weak_evidence", "vague_question"]


class SearchFilter(TypedDict, total=False):
    source_type: str


class WebSearchResult(TypedDict):
    title: str
    url: str
    content: str
    score: float


class GraphSource(TypedDict, total=False):
    index: int
    chunk_id: str
    source: str
    chunk_index: int | None
    page: int | None
    content: str
    score: float | None
    vector_score: float | None
    bm25_score: float | None
    url: str


class GraphConfig(TypedDict):
    configurable: dict[str, str]


class GraphState(TypedDict):
    """State shared between LangGraph nodes."""

    question: str
    messages: Annotated[list[BaseMessage], add_messages]
    question_type: QuestionType
    rewritten_question: str
    documents: list[RetrievalResult]
    context: str
    answer: str
    sources: list[GraphSource]
    retry_count: int
    retrieval_k: int
    score_threshold: float | None
    quality_ok: bool
    quality_reason: str
    retry_strategy: RetryStrategy
    web_search_results: list[WebSearchResult]
    web_context: str
    web_search_error: str
    used_web_search: bool
    web_search_enabled: bool
    search_strategy: SearchStrategy
    search_filter: SearchFilter
    pinned_chunk_ids: list[str]
    excluded_chunk_ids: list[str]

    # 用户侧可信度信息
    evidence_level: EvidenceLevel
    evidence_summary: str
    outcome_category: OutcomeCategory
    used_rerank: bool
    used_rewrite: bool
    token_count: int | None
    prompt_tokens: int | None
    completion_tokens: int | None


class GraphStateUpdate(TypedDict, total=False):
    question: str
    messages: list[BaseMessage]
    question_type: QuestionType
    rewritten_question: str
    documents: list[RetrievalResult]
    context: str
    answer: str
    sources: list[GraphSource]
    retry_count: int
    retrieval_k: int
    score_threshold: float | None
    quality_ok: bool
    quality_reason: str
    retry_strategy: RetryStrategy
    web_search_results: list[WebSearchResult]
    web_context: str
    web_search_error: str
    used_web_search: bool
    web_search_enabled: bool
    search_strategy: SearchStrategy
    search_filter: SearchFilter
    pinned_chunk_ids: list[str]
    excluded_chunk_ids: list[str]
    evidence_level: EvidenceLevel
    evidence_summary: str
    outcome_category: OutcomeCategory
    used_rerank: bool
    used_rewrite: bool
    token_count: int | None
    prompt_tokens: int | None
    completion_tokens: int | None


class RouteDecision(BaseModel):
    """Structured route classification result."""

    question_type: QuestionType = "knowledge_base"
    reason: str = ""


class RerankDecision(BaseModel):
    """Structured rerank result."""

    selected_doc_ids: list[str] = Field(default_factory=list)
    reason: str = ""


class QualityDecision(BaseModel):
    """Structured quality gate result."""

    quality_passed: bool = True
    quality_reason: str = ""
    retry_strategy: Literal["none", "rewrite_query", "expand_retrieval", "insufficient_context"] = "none"
