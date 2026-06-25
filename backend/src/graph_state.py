"""Graph state and Pydantic models for the LangGraph workflow."""

from __future__ import annotations

from typing import Annotated, Any, List, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class GraphState(TypedDict):
    """State shared between LangGraph nodes."""

    question: str
    messages: Annotated[List[BaseMessage], add_messages]
    question_type: str
    rewritten_question: str
    documents: List[Any]
    context: str
    answer: str
    sources: List[dict]
    retry_count: int
    retrieval_k: int
    score_threshold: float | None
    quality_ok: bool
    quality_reason: str
    retry_strategy: str
    web_search_results: List[dict]
    web_context: str
    web_search_error: str
    used_web_search: bool
    web_search_enabled: bool
    search_strategy: str
    search_filter: dict
    pinned_chunk_ids: list[str]
    excluded_chunk_ids: list[str]

    # 用户侧可信度信息
    evidence_level: str
    evidence_summary: str
    outcome_category: str
    used_rerank: bool
    used_rewrite: bool


class RouteDecision(BaseModel):
    """Structured route classification result."""

    question_type: Literal["knowledge_base", "chat_memory", "conversation_summary", "clarification"] = "knowledge_base"
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
