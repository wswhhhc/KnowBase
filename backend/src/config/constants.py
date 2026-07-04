"""Backwards-compatible configuration constants."""

from __future__ import annotations

from src.config import settings as settings_module

SILICONFLOW_API_KEY = settings_module.SILICONFLOW_API_KEY
SILICONFLOW_BASE_URL = settings_module.SILICONFLOW_BASE_URL
EMBEDDING_MODEL = settings_module.EMBEDDING_MODEL
LLM_MODEL = settings_module.LLM_MODEL
LLM_TEMPERATURE = settings_module.LLM_TEMPERATURE
LLM_MAX_TOKENS = settings_module.LLM_MAX_TOKENS
CHROMA_PERSIST_DIR = settings_module.CHROMA_PERSIST_DIR
DATA_DIR = settings_module.DATA_DIR
CHUNK_SIZE = settings_module.CHUNK_SIZE
CHUNK_OVERLAP = settings_module.CHUNK_OVERLAP
TOP_K_RETRIEVAL = settings_module.TOP_K_RETRIEVAL
TOP_K_RERANK = settings_module.TOP_K_RERANK
VECTOR_CANDIDATE_K = settings_module.VECTOR_CANDIDATE_K
RERANK_SCORE_GAP_THRESHOLD = settings_module.RERANK_SCORE_GAP_THRESHOLD
RERANK_QUERY_LENGTH = settings_module.RERANK_QUERY_LENGTH
SCORE_THRESHOLD = settings_module.SCORE_THRESHOLD
RRF_K = settings_module.RRF_K
ENABLE_QUALITY_CHECK = settings_module.ENABLE_QUALITY_CHECK
ENABLE_CONTEXTUAL_RETRIEVAL = settings_module.ENABLE_CONTEXTUAL_RETRIEVAL
MAX_RETRIES = settings_module.MAX_RETRIES
MAX_UPLOAD_MB = settings_module.MAX_UPLOAD_MB
CHECKPOINT_DB_PATH = settings_module.CHECKPOINT_DB_PATH
TAVILY_API_KEY = settings_module.TAVILY_API_KEY
LANGSMITH_TRACING = settings_module.LANGSMITH_TRACING
LANGSMITH_API_KEY = settings_module.LANGSMITH_API_KEY
LANGSMITH_PROJECT = settings_module.LANGSMITH_PROJECT
