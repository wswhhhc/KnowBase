"""Simple local logging and metrics for KnowBase RAG observability.

Records per-query timing, retrieval stats, and quality decisions
into a JSONL log file under ``runtime/local/rag_logs/`` for offline analysis.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from src.config.constants import DATA_DIR

_LOG_DIR = Path(DATA_DIR) / "rag_logs"


def _ensure_log_dir():
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_file() -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return _LOG_DIR / f"rag_{today}.jsonl"


def clear_today_log() -> bool:
    """Delete today's log file if it exists."""
    log_file = _log_file()
    if not log_file.exists():
        return False
    log_file.unlink()
    return True


def quality_fail_rate(df, recent_n: int | None = None) -> float:
    """Return quality fail rate percentage for full or recent-N rows."""
    import pandas as pd

    if df.empty or "quality_ok" not in df.columns:
        return 0.0
    working = df.sort_values("timestamp", ascending=False) if "timestamp" in df.columns else df
    if recent_n is not None and recent_n > 0:
        working = working.head(recent_n)
    if working.empty:
        return 0.0
    return (1 - working["quality_ok"].astype(float).mean()) * 100


def log_query(
    *,
    question: str,
    thread_id: str,
    question_type: str,
    retrieval_count: int,
    retry_count: int,
    quality_ok: bool,
    quality_reason: str,
    source_count: int,
    elapsed_ms: int,
    answer: str,
    error: str = "",
    token_count: int | None = None,
    retrieval_k: int | None = None,
    used_web_search: bool | None = None,
    used_rerank: bool | None = None,
    used_rewrite: bool | None = None,
    ttfb_ms: int = 0,
    first_token_ms: int = 0,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    llm_model: str | None = None,
) -> None:
    """Append one query record to the daily log file."""
    _ensure_log_dir()
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "thread_id": thread_id,
        "question": question[:100],
        "question_type": question_type,
        "retrieval_count": retrieval_count,
        "retry_count": retry_count,
        "quality_ok": quality_ok,
        "quality_reason": quality_reason,
        "source_count": source_count,
        "elapsed_ms": elapsed_ms,
        "answer_preview": answer[:200],
        "error": error,
        "token_count": token_count,
        "retrieval_k": retrieval_k,
        "used_web_search": used_web_search,
        "used_rerank": used_rerank,
        "used_rewrite": used_rewrite,
        "ttfb_ms": ttfb_ms,
        "first_token_ms": first_token_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "llm_model": llm_model,
    }
    with open(_log_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
