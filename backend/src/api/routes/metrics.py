"""Metrics — query log retrieval for dashboard."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Query

from config.settings import ROOT_DIR
from src.api.models import QueryLogEntry

router = APIRouter()
_LOG_DIR = ROOT_DIR / "data" / "rag_logs"


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
    records.sort(key=lambda r: r.timestamp, reverse=True)
    return records[:limit]


@router.delete("/logs/today")
async def clear_today():
    from src.metrics import clear_today_log
    return {"ok": True, "cleared": clear_today_log()}
