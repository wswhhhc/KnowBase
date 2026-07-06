"""One-time SQLite business data import into the configured SQLAlchemy database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, text

from src.persistence.schema import bookmarks, conversations, messages, pinned_sources, workspaces
from src.persistence.sqlalchemy_database import create_engine_for_url


TABLE_ORDER = (workspaces, conversations, messages, bookmarks, pinned_sources)
INTEGER_ID_TABLES = (messages, bookmarks, pinned_sources)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _source_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def _source_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    return {row["name"] for row in rows}


def _read_source_rows(sqlite_path: Path) -> dict[str, list[dict]]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        table_names = _source_table_names(conn)
        rows_by_table: dict[str, list[dict]] = {}
        for table in TABLE_ORDER:
            if table.name not in table_names:
                rows_by_table[table.name] = []
                continue

            source_columns = _source_columns(conn, table.name)
            column_names = [column.name for column in table.columns if column.name in source_columns]
            if not column_names:
                rows_by_table[table.name] = []
                continue

            selected = ", ".join(_quote_identifier(column) for column in column_names)
            order_column = "id" if "id" in source_columns else "rowid"
            query = (
                f"SELECT {selected} FROM {_quote_identifier(table.name)} "
                f"ORDER BY {_quote_identifier(order_column)}"
            )
            rows_by_table[table.name] = [dict(row) for row in conn.execute(query).fetchall()]
        return rows_by_table
    finally:
        conn.close()


def _reset_postgres_sequences(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table in INTEGER_ID_TABLES:
            conn.execute(
                text(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE(MAX(id), 1), "
                    f"MAX(id) IS NOT NULL"
                    f") FROM {table.name}"
                )
            )


def import_sqlite_business_data(
    sqlite_path: str | Path,
    database_url: str,
    *,
    truncate: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """Copy Phase 1 business tables from a SQLite database to ``database_url``.

    The import preserves primary keys. Use ``truncate=True`` for a clean target
    import; otherwise existing target rows may conflict with source IDs.
    """
    source_path = Path(sqlite_path)
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    rows_by_table = _read_source_rows(source_path)
    counts = {table_name: len(rows) for table_name, rows in rows_by_table.items()}
    if dry_run:
        return counts

    engine = create_engine_for_url(database_url)
    with engine.begin() as conn:
        if truncate:
            for table in reversed(TABLE_ORDER):
                conn.execute(table.delete())
        for table in TABLE_ORDER:
            rows = rows_by_table[table.name]
            if rows:
                conn.execute(table.insert(), rows)
    _reset_postgres_sequences(engine)
    return counts
