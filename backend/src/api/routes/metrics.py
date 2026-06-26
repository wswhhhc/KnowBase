"""Metrics — query log retrieval for dashboard."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from config.settings import ROOT_DIR
from src.api.deps import verify_api_key
from src.api.models import QueryLogEntry, QueryLogsResponse
from src.conversations import list_assistant_debug_pairs

router = APIRouter(dependencies=[Depends(verify_api_key)])
_LOG_DIR = ROOT_DIR / "data" / "rag_logs"

_MODEL_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "deepseek": (0.5, 2.0),
    "gpt-4": (35.0, 70.0),
    "gpt-4o": (18.0, 72.0),
    "qwen": (2.0, 8.0),
    "glm": (2.5, 10.0),
    "default": (1.5, 6.0),
}


def _apply_debug_web_search_flags(records: list[QueryLogEntry]) -> list[QueryLogEntry]:
    """Correct stale log flags using persisted per-message debug info."""
    if not records:
        return records

    flags_by_key: dict[tuple[str, str], deque[bool]] = defaultdict(deque)
    for pair in sorted(list_assistant_debug_pairs(), key=lambda item: item["created_at"]):
        key = (pair["thread_id"], pair["question"])
        flags_by_key[key].append(bool(pair["debug_info"].get("used_web_search", False)))

    for entry in sorted(records, key=lambda item: item.timestamp):
        key = (entry.thread_id, entry.question)
        if flags_by_key[key]:
            entry.used_web_search = flags_by_key[key].popleft()

    return records


def _pricing_for_model(model_name: str | None) -> tuple[float, float]:
    normalized = (model_name or "").lower()
    for prefix, pricing in sorted(
        _MODEL_PRICING_PER_MILLION.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if prefix != "default" and prefix in normalized:
            return pricing
    return _MODEL_PRICING_PER_MILLION["default"]


def _estimate_record_cost(record: QueryLogEntry) -> float:
    prompt_price, completion_price = _pricing_for_model(record.llm_model)
    prompt_tokens = int(record.prompt_tokens or 0)
    completion_tokens = int(record.completion_tokens or 0)

    if prompt_tokens == 0 and completion_tokens == 0 and record.token_count:
        prompt_tokens = int(record.token_count)

    return (prompt_tokens / 1_000_000) * prompt_price + (completion_tokens / 1_000_000) * completion_price


def _load_query_logs(days: int, limit: int) -> list[QueryLogEntry]:
    records: list[QueryLogEntry] = []
    cutoff = datetime.now(UTC) - timedelta(days=days)
    if not _LOG_DIR.exists():
        return []
    for f in sorted(_LOG_DIR.glob("rag_*.jsonl"), reverse=True):
        if len(records) >= limit:
            break
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entry = QueryLogEntry(**json.loads(line))
                        if datetime.fromisoformat(entry.timestamp) >= cutoff:
                            records.append(entry)
                    except Exception:
                        pass
    _apply_debug_web_search_flags(records)
    records.sort(key=lambda r: r.timestamp, reverse=True)
    return records[:limit]


@router.get("/logs")
async def query_logs(days: int = Query(7, ge=1, le=90), limit: int = Query(500, ge=1, le=5000)) -> QueryLogsResponse:
    records = _load_query_logs(days, limit)
    total_cost = 0.0
    total_tokens = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for entry in records:
        entry.estimated_cost = round(_estimate_record_cost(entry), 6)
        total_cost += entry.estimated_cost
        total_tokens += int(entry.token_count or 0)
        total_prompt_tokens += int(entry.prompt_tokens or 0)
        total_completion_tokens += int(entry.completion_tokens or 0)

    return QueryLogsResponse(
        logs=records,
        total_cost=round(total_cost, 6),
        total_tokens=total_tokens,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
    )


@router.delete("/logs/today")
async def clear_today():
    from src.metrics import clear_today_log
    return {"ok": True, "cleared": clear_today_log()}
