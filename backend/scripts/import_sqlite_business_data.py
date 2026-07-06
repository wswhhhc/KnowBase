"""Import Phase 1 business data from SQLite into DATABASE_URL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.config.settings import settings
from src.persistence.sqlite_import import import_sqlite_business_data


DEFAULT_SQLITE_PATH = REPO_ROOT / "runtime" / "local" / "conversations.db"


def _run_migrations(database_url: str) -> None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import KnowBase Phase 1 business tables from SQLite into DATABASE_URL."
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(DEFAULT_SQLITE_PATH),
        help="Source SQLite conversations.db path.",
    )
    parser.add_argument(
        "--database-url",
        default=settings.storage.database_url,
        help="Target SQLAlchemy database URL. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete target Phase 1 business rows before importing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print source row counts without writing to the target database.",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Do not run Alembic migrations on the target before importing.",
    )
    args = parser.parse_args()

    if not args.skip_migrations and not args.dry_run:
        _run_migrations(args.database_url)

    counts = import_sqlite_business_data(
        args.sqlite_path,
        args.database_url,
        truncate=args.truncate,
        dry_run=args.dry_run,
    )
    for table_name, count in counts.items():
        print(f"{table_name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
