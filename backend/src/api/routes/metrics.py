"""Metrics — query log retrieval for dashboard."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from config.settings import ROOT_DIR
from src.api.deps import verify_api_key
from src.api.models import QueryLogEntry
from src.conversations import list_assistant_debug_pairs

router = APIRouter(dependencies=[Depends(verify_api_key)])
_LOG_DIR = ROOT_DIR / "data" / "rag_logs"


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


@router.get("/logs")
async def query_logs(days: int = Query(7, ge=1, le=90), limit: int = Query(500, ge=1, le=5000)) -> list[QueryLogEntry]:
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


@router.delete("/logs/today")
async def clear_today():
    from src.metrics import clear_today_log
    return {"ok": True, "cleared": clear_today_log()}
