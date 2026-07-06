from __future__ import annotations

from src.persistence import audit_store
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def test_audit_store_records_and_lists_events(monkeypatch, tmp_path):
    database_url = f"sqlite:///{tmp_path / 'audit.db'}"
    engine = create_engine_for_url(database_url)
    metadata.create_all(engine)
    monkeypatch.setattr(audit_store.settings, "database_url", database_url)

    event = audit_store.record_event(
        action="auth.login_succeeded",
        actor_user_id="user-1",
        target_type="user",
        target_id="user-1",
        metadata={"username": "admin"},
    )
    events = audit_store.list_events(actor_user_id="user-1")

    assert event is not None
    assert event["action"] == "auth.login_succeeded"
    assert event["metadata"] == {"username": "admin"}
    assert events == [event]
