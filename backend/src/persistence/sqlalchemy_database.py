"""SQLAlchemy database helpers for the team-edition persistence path."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import settings


def is_postgres_url(database_url: str) -> bool:
    """Return whether the SQLAlchemy URL targets PostgreSQL."""
    return database_url.startswith(("postgresql://", "postgresql+"))


def create_engine_for_url(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with conservative production defaults."""
    kwargs: dict[str, object] = {"future": True}
    if database_url.startswith("sqlite:"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(database_url, **kwargs)


@lru_cache(maxsize=4)
def get_engine(database_url: str | None = None) -> Engine:
    """Return a cached engine for the configured SQLAlchemy database URL."""
    return create_engine_for_url(database_url or settings.storage.database_url)


@lru_cache(maxsize=4)
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    """Return a cached session factory for API services and workers."""
    return sessionmaker(
        bind=get_engine(database_url),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    """Provide a transactional SQLAlchemy session boundary."""
    session = get_session_factory(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

