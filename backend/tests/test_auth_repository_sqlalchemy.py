from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.auth_repository import (
    create_refresh_token_with_session,
    create_user_with_session,
    get_refresh_token_with_session,
    get_user_by_id_with_session,
    get_user_by_username_with_session,
    revoke_refresh_token_with_session,
)
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def _session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def test_sqlalchemy_create_and_get_user_omits_password_hash_from_create_result():
    session_factory = _session_factory()

    created = create_user_with_session(
        session_factory,
        username="admin",
        password_hash="hash",
        role="admin",
    )
    by_username = get_user_by_username_with_session(session_factory, "admin")
    by_id = get_user_by_id_with_session(session_factory, created["id"])

    assert "password_hash" not in created
    assert by_username is not None
    assert by_username["password_hash"] == "hash"
    assert by_id is not None
    assert by_id["username"] == "admin"


def test_sqlalchemy_refresh_token_can_be_revoked():
    session_factory = _session_factory()
    user = create_user_with_session(session_factory, username="viewer", password_hash="hash")
    token = create_refresh_token_with_session(
        session_factory,
        user_id=user["id"],
        token_hash="token-hash",
        expires_at="2099-01-01T00:00:00+00:00",
    )

    stored = get_refresh_token_with_session(session_factory, "token-hash")
    revoked = revoke_refresh_token_with_session(session_factory, "token-hash")
    after = get_refresh_token_with_session(session_factory, "token-hash")

    assert stored is not None
    assert stored["id"] == token["id"]
    assert revoked is True
    assert after is not None
    assert after["revoked_at"] is not None
