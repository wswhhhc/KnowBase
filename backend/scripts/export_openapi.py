"""Export the current FastAPI OpenAPI schema to backend/openapi.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.api.main import app


OUTPUT_PATH = BACKEND_ROOT / "openapi.json"


def main() -> int:
    schema = app.openapi()
    OUTPUT_PATH.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote OpenAPI schema to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
