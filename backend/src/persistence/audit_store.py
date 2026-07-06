"""Audit persistence facade for security-relevant events."""

from __future__ import annotations

import logging

from src.config.settings import settings
from src.persistence import audit_repository
from src.persistence.sqlalchemy_database import get_session_factory


logger = logging.getLogger(__name__)


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def record_event(
    *,
    action: str,
    actor_user_id: str | None = None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict | None = None,
) -> dict | None:
    try:
        return audit_repository.record_audit_log_with_session(
            _session_factory(),
            action=action,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning("Failed to write audit log for %s: %s", action, exc)
        return None


def list_events(*, actor_user_id: str | None = None, limit: int = 100) -> list[dict]:
    return audit_repository.list_audit_logs_with_session(
        _session_factory(),
        actor_user_id=actor_user_id,
        limit=limit,
    )
