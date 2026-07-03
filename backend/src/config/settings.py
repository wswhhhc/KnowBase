"""Typed application settings for KnowBase."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class LLMSettings(BaseModel):
    """Layered view for model and embedding configuration."""

    api_key: str
    base_url: str
    embedding_model: str
    model: str
    temperature: float
    max_tokens: int


class RetrievalSettings(BaseModel):
    """Layered view for retrieval and chunking knobs."""

    contextual_retrieval_enabled: bool
    chunk_size: int
    chunk_overlap: int
    top_k: int
    rerank_top_k: int
    vector_candidate_k: int
    rerank_score_gap_threshold: float
    rerank_query_length: int
    score_threshold: float | None
    rrf_k: int


class QualitySettings(BaseModel):
    """Layered view for quality gates and upload safety limits."""

    enabled: bool
    max_retries: int
    max_upload_mb: int


class ObservabilitySettings(BaseModel):
    """Layered view for LangSmith tracing configuration."""

    tracing_enabled: bool
    api_key: str
    project: str


class ExternalServiceSettings(BaseModel):
    """Layered view for optional external integrations."""

    tavily_api_key: str


class AuthSettings(BaseModel):
    """Layered view for backend auth configuration."""

    api_key: str


class StorageSettings(BaseModel):
    """Layered view for local persistence paths."""

    chroma_persist_dir: Path
    data_dir: Path
    checkpoint_db_path: str


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

    enable_contextual_retrieval: bool = Field(default=True, validation_alias="ENABLE_CONTEXTUAL_RETRIEVAL")
    chunk_size: int = Field(default=1500, validation_alias="CHUNK_SIZE")
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

    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("API_KEY", "KNOWBASE_API_KEY"),
    )

    chat_stream_rate_limit_per_minute: int = Field(
        default=12,
        validation_alias="CHAT_STREAM_RATE_LIMIT_PER_MINUTE",
    )
    document_import_rate_limit_per_minute: int = Field(
        default=6,
        validation_alias="DOCUMENT_IMPORT_RATE_LIMIT_PER_MINUTE",
    )

    checkpoint_db_path: str = Field(
        default=str(ROOT_DIR / "data" / "checkpoints.db"),
        validation_alias="CHECKPOINT_DB_PATH",
    )

    @field_validator("chroma_persist_dir", "data_dir", mode="before")
    @classmethod
    def _resolve_path(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT_DIR / path

    @field_validator(
        "chunk_size",
        "top_k_retrieval",
        "top_k_rerank",
        "vector_candidate_k",
        "max_upload_mb",
        "chat_stream_rate_limit_per_minute",
        "document_import_rate_limit_per_minute",
    )
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

    @property
    def llm(self) -> LLMSettings:
        return LLMSettings(
            api_key=self.siliconflow_api_key,
            base_url=self.siliconflow_base_url,
            embedding_model=self.embedding_model,
            model=self.llm_model,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
        )

    @property
    def retrieval(self) -> RetrievalSettings:
        return RetrievalSettings(
            contextual_retrieval_enabled=self.enable_contextual_retrieval,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            top_k=self.top_k_retrieval,
            rerank_top_k=self.top_k_rerank,
            vector_candidate_k=self.vector_candidate_k,
            rerank_score_gap_threshold=self.rerank_score_gap_threshold,
            rerank_query_length=self.rerank_query_length,
            score_threshold=self.score_threshold,
            rrf_k=self.rrf_k,
        )

    @property
    def quality(self) -> QualitySettings:
        return QualitySettings(
            enabled=self.enable_quality_check,
            max_retries=self.max_retries,
            max_upload_mb=self.max_upload_mb,
        )

    @property
    def observability(self) -> ObservabilitySettings:
        return ObservabilitySettings(
            tracing_enabled=self.langsmith_tracing,
            api_key=self.langsmith_api_key,
            project=self.langsmith_project,
        )

    @property
    def external_services(self) -> ExternalServiceSettings:
        return ExternalServiceSettings(tavily_api_key=self.tavily_api_key)

    @property
    def auth(self) -> AuthSettings:
        return AuthSettings(api_key=self.api_key)

    @property
    def storage(self) -> StorageSettings:
        return StorageSettings(
            chroma_persist_dir=self.chroma_persist_dir,
            data_dir=self.data_dir,
            checkpoint_db_path=self.checkpoint_db_path,
        )


settings = Settings()
_RUNTIME_SETTINGS_PATH = ROOT_DIR / "data" / "runtime_settings.json"
_runtime_overrides: dict[str, str | float | bool | int] = {}
_MISSING = object()
MASKED_SECRET_VALUE = "__KEEP_EXISTING_SECRET__"


def _load_runtime_settings():
    global _runtime_overrides
    try:
        if _RUNTIME_SETTINGS_PATH.exists():
            with open(_RUNTIME_SETTINGS_PATH, encoding="utf-8") as f:
                _runtime_overrides = json.load(f)
    except Exception:
        _runtime_overrides = {}


def get_runtime_setting(key: str, default=_MISSING):
    """Return the runtime-overridden value, or fall back to settings."""
    if key in _runtime_overrides:
        return _runtime_overrides[key]
    if default is _MISSING:
        return getattr(settings, key, None)
    return getattr(settings, key, default)


def update_runtime_settings(values: dict):
    """Persist runtime config overrides to JSON file."""
    global _runtime_overrides
    merged = settings.model_dump()
    merged.update(_runtime_overrides)
    merged.update(values)
    validated = Settings.model_validate(merged)
    normalized = {key: getattr(validated, key) for key in values}
    _runtime_overrides.update(normalized)
    _RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_RUNTIME_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(_runtime_overrides, f, ensure_ascii=False, indent=2)


def get_all_settings() -> dict:
    """Return all user-facing config (env defaults merged with runtime overrides)."""
    return {k: get_runtime_setting(k) for k in _USER_FACING_SETTINGS}


def get_public_settings() -> dict:
    """Return UI-safe settings, masking secrets instead of exposing raw values."""
    data = get_all_settings()
    for key in _SECRET_SETTINGS:
        value = str(data.get(key, "") or "")
        data[key] = MASKED_SECRET_VALUE if value else ""
    return data


# Keys exposed in the settings UI
_USER_FACING_SETTINGS = [
    "siliconflow_api_key", "siliconflow_base_url",
    "embedding_model", "llm_model", "llm_temperature",
    "tavily_api_key", "api_key",
    "chunk_size", "chunk_overlap", "top_k_retrieval", "top_k_rerank",
    "enable_quality_check", "enable_contextual_retrieval",
]
_SECRET_SETTINGS = {"siliconflow_api_key", "tavily_api_key", "api_key"}


_load_runtime_settings()

if settings.langsmith_tracing:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.observability.project)
    if settings.observability.api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.observability.api_key)


def _is_configured_api_key(api_key: str) -> bool:
    """Return whether the key looks like a real configured secret."""
    return bool(api_key) and api_key != "你的 API Key" and len(api_key.strip()) >= 10


def require_siliconflow_api_key() -> str:
    """Return a configured API key or raise a user-actionable error."""
    api_key = get_runtime_setting("siliconflow_api_key", settings.llm.api_key)
    if not _is_configured_api_key(api_key):
        raise ValueError(
            "缺少硅基流动 API Key。请在 .env 中配置 SILICONFLOW_API_KEY=你的密钥，"
            "或设置系统环境变量 SILICONFLOW_API_KEY。"
        )
    return api_key


# Backwards-compatible constants for existing imports.
SILICONFLOW_API_KEY = settings.llm.api_key
SILICONFLOW_BASE_URL = settings.llm.base_url
EMBEDDING_MODEL = settings.llm.embedding_model
LLM_MODEL = settings.llm.model
LLM_TEMPERATURE = settings.llm.temperature
LLM_MAX_TOKENS = settings.llm.max_tokens
CHROMA_PERSIST_DIR = str(settings.storage.chroma_persist_dir)
DATA_DIR = str(settings.storage.data_dir)
CHUNK_SIZE = settings.retrieval.chunk_size
CHUNK_OVERLAP = settings.retrieval.chunk_overlap
TOP_K_RETRIEVAL = settings.retrieval.top_k
TOP_K_RERANK = settings.retrieval.rerank_top_k
VECTOR_CANDIDATE_K = settings.retrieval.vector_candidate_k
RERANK_SCORE_GAP_THRESHOLD = settings.retrieval.rerank_score_gap_threshold
RERANK_QUERY_LENGTH = settings.retrieval.rerank_query_length
SCORE_THRESHOLD = settings.retrieval.score_threshold
RRF_K = settings.retrieval.rrf_k
ENABLE_QUALITY_CHECK = settings.quality.enabled
ENABLE_CONTEXTUAL_RETRIEVAL = settings.retrieval.contextual_retrieval_enabled
MAX_RETRIES = settings.quality.max_retries
MAX_UPLOAD_MB = settings.quality.max_upload_mb
CHECKPOINT_DB_PATH = settings.storage.checkpoint_db_path
TAVILY_API_KEY = settings.external_services.tavily_api_key
LANGSMITH_TRACING = settings.observability.tracing_enabled
LANGSMITH_API_KEY = settings.observability.api_key
LANGSMITH_PROJECT = settings.observability.project
