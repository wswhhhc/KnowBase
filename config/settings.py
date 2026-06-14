"""Typed application settings for KnowBase."""

import os
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    siliconflow_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("SILICONFLOW_API_KEY", "CHROMA_API_KEY"),
    )
    siliconflow_base_url: str = Field(
        default="https://api.siliconflow.cn/v1",
        validation_alias="SILICONFLOW_BASE_URL",
    )
    embedding_model: str = Field(default="BAAI/bge-m3", validation_alias="EMBEDDING_MODEL")
    llm_model: str = Field(default="deepseek-ai/DeepSeek-V4-Flash", validation_alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.3, validation_alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, validation_alias="LLM_MAX_TOKENS")

    chroma_persist_dir: Path = Field(
        default=ROOT_DIR / "data" / "chroma_db",
        validation_alias="CHROMA_PERSIST_DIR",
    )
    data_dir: Path = Field(default=ROOT_DIR / "data", validation_alias="DATA_DIR")

    chunk_size: int = Field(default=800, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, validation_alias="CHUNK_OVERLAP")
    top_k_retrieval: int = Field(default=5, validation_alias="TOP_K_RETRIEVAL")
    top_k_rerank: int = Field(default=3, validation_alias="TOP_K_RERANK")
    vector_candidate_k: int = Field(default=30, validation_alias="VECTOR_CANDIDATE_K")
    rerank_score_gap_threshold: float = Field(default=0.005, validation_alias="RERANK_SCORE_GAP_THRESHOLD")
    rerank_query_length: int = Field(default=50, validation_alias="RERANK_QUERY_LENGTH")
    score_threshold: float | None = Field(default=None, validation_alias="SCORE_THRESHOLD")
    rrf_k: int = Field(default=60, validation_alias="RRF_K")

    enable_quality_check: bool = Field(default=True, validation_alias="ENABLE_QUALITY_CHECK")
    max_retries: int = Field(default=2, validation_alias="MAX_RETRIES")
    max_upload_mb: int = Field(default=5, validation_alias="MAX_UPLOAD_MB")

    langsmith_tracing: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")
    langsmith_api_key: str = Field(default="", validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="knowbase", validation_alias="LANGSMITH_PROJECT")

    tavily_api_key: str = Field(default="", validation_alias="TAVILY_API_KEY")

    checkpoint_db_path: str = Field(
        default=str(ROOT_DIR / "data" / "checkpoints.db"),
        validation_alias="CHECKPOINT_DB_PATH",
    )

    @field_validator("chroma_persist_dir", "data_dir", mode="before")
    @classmethod
    def _resolve_path(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT_DIR / path

    @field_validator("chunk_size", "top_k_retrieval", "top_k_rerank", "vector_candidate_k", "max_upload_mb")
    @classmethod
    def _positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value

    @field_validator("chunk_overlap")
    @classmethod
    def _non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be greater than or equal to 0")
        return value


settings = Settings()

if settings.langsmith_tracing:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)


def _is_configured_api_key(api_key: str) -> bool:
    """Return whether the key looks like a real configured secret."""
    return bool(api_key) and api_key != "你的 API Key" and len(api_key.strip()) >= 10


def require_siliconflow_api_key() -> str:
    """Return a configured API key or raise a user-actionable error."""
    if not _is_configured_api_key(settings.siliconflow_api_key):
        raise ValueError(
            "缺少硅基流动 API Key。请在 .env 中配置 SILICONFLOW_API_KEY=你的密钥，"
            "或设置系统环境变量 SILICONFLOW_API_KEY。"
        )
    return settings.siliconflow_api_key


# Backwards-compatible constants for existing imports.
SILICONFLOW_API_KEY = settings.siliconflow_api_key
SILICONFLOW_BASE_URL = settings.siliconflow_base_url
EMBEDDING_MODEL = settings.embedding_model
LLM_MODEL = settings.llm_model
LLM_TEMPERATURE = settings.llm_temperature
LLM_MAX_TOKENS = settings.llm_max_tokens
CHROMA_PERSIST_DIR = str(settings.chroma_persist_dir)
DATA_DIR = str(settings.data_dir)
CHUNK_SIZE = settings.chunk_size
CHUNK_OVERLAP = settings.chunk_overlap
TOP_K_RETRIEVAL = settings.top_k_retrieval
TOP_K_RERANK = settings.top_k_rerank
VECTOR_CANDIDATE_K = settings.vector_candidate_k
RERANK_SCORE_GAP_THRESHOLD = settings.rerank_score_gap_threshold
RERANK_QUERY_LENGTH = settings.rerank_query_length
SCORE_THRESHOLD = settings.score_threshold
RRF_K = settings.rrf_k
ENABLE_QUALITY_CHECK = settings.enable_quality_check
MAX_RETRIES = settings.max_retries
MAX_UPLOAD_MB = settings.max_upload_mb
CHECKPOINT_DB_PATH = settings.checkpoint_db_path
TAVILY_API_KEY = settings.tavily_api_key
LANGSMITH_TRACING = settings.langsmith_tracing
LANGSMITH_API_KEY = settings.langsmith_api_key
LANGSMITH_PROJECT = settings.langsmith_project
