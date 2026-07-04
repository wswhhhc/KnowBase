"""Backwards-compatible configuration constants."""

from __future__ import annotations

from src.config.settings import settings

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
