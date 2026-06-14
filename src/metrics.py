"""Simple local logging and metrics for KnowBase RAG observability.

Records per-query timing, retrieval stats, and quality decisions
into a JSONL log file under ``data/rag_logs/`` for offline analysis.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from config.settings import ROOT_DIR


_LOG_DIR = ROOT_DIR / "data" / "rag_logs"


def _ensure_log_dir():
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_file() -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return _LOG_DIR / f"rag_{today}.jsonl"


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
) -> None:
    """Append one query record to the daily log file."""
    _ensure_log_dir()
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "thread_id": thread_id,
        "question": question,
        "question_type": question_type,
        "retrieval_count": retrieval_count,
        "retry_count": retry_count,
        "quality_ok": quality_ok,
        "quality_reason": quality_reason,
        "source_count": source_count,
        "elapsed_ms": elapsed_ms,
        "answer_preview": answer[:200],
        "error": error,
    }
    with open(_log_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
