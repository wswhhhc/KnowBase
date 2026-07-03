"""Keep the committed OpenAPI snapshot aligned with the live FastAPI schema."""

from __future__ import annotations

import json
from pathlib import Path

from src.api.main import app


SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def test_openapi_snapshot_matches_current_app_schema():
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    current = app.openapi()

    assert snapshot == current, (
        "backend/openapi.json is out of date. "
        "Run `uv run python backend/scripts/export_openapi.py` and commit the regenerated snapshot."
    )
