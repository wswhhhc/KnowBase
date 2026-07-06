from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.auth_repository import (
    count_active_admins_with_session,
    create_refresh_token_with_session,
    create_user_with_session,
    get_refresh_token_with_session,
    get_user_by_id_with_session,
    get_user_by_username_with_session,
    list_workspace_memberships_for_user_with_session,
    list_users_with_session,
    revoke_refresh_tokens_for_user_with_session,
    revoke_refresh_token_with_session,
    update_user_with_session,
    delete_user_with_session,
    get_workspace_member_role_with_session,
    list_workspace_members_with_session,
    replace_workspace_members_with_session,
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


def test_sqlalchemy_list_update_and_delete_user():
    session_factory = _session_factory()
    user = create_user_with_session(session_factory, username="viewer", password_hash="hash")

    listed = list_users_with_session(session_factory)
    updated = update_user_with_session(
        session_factory,
        user["id"],
        username="editor",
        password_hash="new-hash",
        role="editor",
        is_active=False,
    )
    stored = get_user_by_id_with_session(session_factory, user["id"])
    deleted = delete_user_with_session(session_factory, user["id"])

    assert listed[0]["username"] == "viewer"
    assert "password_hash" not in listed[0]
    assert updated is not None
    assert updated["username"] == "editor"
    assert "password_hash" not in updated
    assert stored is not None
    assert stored["password_hash"] == "new-hash"
    assert stored["role"] == "editor"
    assert stored["is_active"] is False
    assert deleted is True
    assert get_user_by_id_with_session(session_factory, user["id"]) is None


def test_sqlalchemy_counts_only_active_admin_users():
    session_factory = _session_factory()
    create_user_with_session(session_factory, username="admin", password_hash="hash", role="admin")
    create_user_with_session(
        session_factory,
        username="disabled-admin",
        password_hash="hash",
        role="admin",
        is_active=False,
    )
    create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")

    assert count_active_admins_with_session(session_factory) == 1


def test_sqlalchemy_revoke_refresh_tokens_for_user_only_revokes_target_user():
    session_factory = _session_factory()
    viewer = create_user_with_session(session_factory, username="viewer", password_hash="hash")
    editor = create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")
    create_refresh_token_with_session(
        session_factory,
        user_id=viewer["id"],
        token_hash="viewer-token-a",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    create_refresh_token_with_session(
        session_factory,
        user_id=viewer["id"],
        token_hash="viewer-token-b",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    create_refresh_token_with_session(
        session_factory,
        user_id=editor["id"],
        token_hash="editor-token",
        expires_at="2099-01-01T00:00:00+00:00",
    )

    revoked = revoke_refresh_tokens_for_user_with_session(session_factory, viewer["id"])

    assert revoked == 2
    assert get_refresh_token_with_session(session_factory, "viewer-token-a")["revoked_at"] is not None
    assert get_refresh_token_with_session(session_factory, "viewer-token-b")["revoked_at"] is not None
    assert get_refresh_token_with_session(session_factory, "editor-token")["revoked_at"] is None


def test_sqlalchemy_delete_user_cleans_memberships_and_refresh_tokens():
    session_factory = _session_factory()
    viewer = create_user_with_session(session_factory, username="viewer", password_hash="hash")
    create_refresh_token_with_session(
        session_factory,
        user_id=viewer["id"],
        token_hash="viewer-token",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    replace_workspace_members_with_session(
        session_factory,
        workspace_id="ws-a",
        members=[{"user_id": viewer["id"], "role": "viewer"}],
    )

    deleted = delete_user_with_session(session_factory, viewer["id"])

    assert deleted is True
    assert get_refresh_token_with_session(session_factory, "viewer-token") is None
    assert list_workspace_memberships_for_user_with_session(session_factory, viewer["id"]) == []


def test_sqlalchemy_replace_and_list_workspace_members():
    session_factory = _session_factory()
    editor = create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")
    viewer = create_user_with_session(session_factory, username="viewer", password_hash="hash", role="viewer")

    members = replace_workspace_members_with_session(
        session_factory,
        workspace_id="ws-a",
        members=[
            {"user_id": editor["id"], "role": "editor"},
            {"user_id": viewer["id"], "role": "viewer"},
        ],
    )
    role = get_workspace_member_role_with_session(
        session_factory,
        workspace_id="ws-a",
        user_id=editor["id"],
    )

    assert [member["username"] for member in members] == ["editor", "viewer"]
    assert [member["role"] for member in members] == ["editor", "viewer"]
    assert role == "editor"

    replaced = replace_workspace_members_with_session(
        session_factory,
        workspace_id="ws-a",
        members=[{"user_id": viewer["id"], "role": "editor"}],
    )

    assert replaced == list_workspace_members_with_session(session_factory, "ws-a")
    assert len(replaced) == 1
    assert replaced[0]["user_id"] == viewer["id"]
