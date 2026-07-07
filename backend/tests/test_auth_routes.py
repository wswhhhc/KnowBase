from __future__ import annotations

from fastapi.testclient import TestClient
from unittest.mock import patch

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import audit_store, auth_store, database, workspace_store
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def _configure_auth_database(monkeypatch, tmp_path):
    db_path = tmp_path / "auth.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine_for_url(database_url)
    metadata.create_all(engine)
    monkeypatch.setattr(database, "_DB_PATH_OVERRIDE", db_path)
    monkeypatch.setattr(auth_store.settings, "database_url", database_url)
    monkeypatch.setattr(audit_store.settings, "database_url", database_url)
    monkeypatch.setattr(workspace_store.settings, "database_url", database_url)
    monkeypatch.setattr(auth_store.settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(auth_store.settings, "access_token_minutes", 15)
    monkeypatch.setattr(auth_store.settings, "refresh_token_days", 14)
    return database_url


def test_login_me_refresh_and_logout_flow(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    user = auth_store.create_user(
        username="admin",
        password_hash=hash_password("pw"),
        role="admin",
    )

    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})

    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["id"] == user["id"]
    assert "password_hash" not in body["user"]
    audit_events = audit_store.list_events(actor_user_id=user["id"])
    assert audit_events[0]["action"] == "auth.login_succeeded"
    assert audit_events[0]["metadata"] == {"role": "admin", "username": "admin"}

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    refresh = client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refresh.status_code == 200
    refreshed = refresh.json()
    assert refreshed["refresh_token"] != body["refresh_token"]

    reused = client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert reused.status_code == 401

    logout = client.post("/api/auth/logout", json={"refresh_token": refreshed["refresh_token"]})
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}

    audit_events = audit_store.list_events(actor_user_id=user["id"], limit=10)
    actions = [event["action"] for event in audit_events]
    assert "auth.refresh_succeeded" in actions
    assert "auth.refresh_failed" in actions
    assert "auth.logout_succeeded" in actions
    for event in audit_events:
        assert "refresh_token" not in event["metadata"]
        assert "token_hash" not in event["metadata"]


def test_login_rejects_bad_password(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("pw"), role="admin")

    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})

    assert response.status_code == 401
    audit_events = audit_store.list_events()
    assert audit_events[0]["action"] == "auth.login_failed"
    assert audit_events[0]["target_id"] == "admin"
    assert "password" not in audit_events[0]["metadata"]


def test_register_creates_isolated_editor_workspace(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)

    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={"username": "  alice  ", "password": "alice-pass"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "alice"
    assert body["user"]["role"] == "editor"
    assert body["user"]["is_active"] is True
    assert "password_hash" not in body["user"]
    stored = auth_store.get_user_by_username("alice")
    assert stored is not None
    assert auth_store.get_workspace_member_role(workspace_id="", user_id=stored["id"]) is None

    workspaces = client.get(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert workspaces.status_code == 200
    visible_workspaces = workspaces.json()
    assert len(visible_workspaces) == 1
    personal_workspace = visible_workspaces[0]
    assert personal_workspace["id"]
    assert personal_workspace["name"] == "alice 的工作区"
    assert auth_store.get_workspace_member_role(
        workspace_id=personal_workspace["id"],
        user_id=stored["id"],
    ) == "editor"

    audit_events = audit_store.list_events(actor_user_id=stored["id"], limit=10)
    assert audit_events[0]["action"] == "auth.register_succeeded"
    assert audit_events[0]["metadata"] == {
        "personal_workspace_id": personal_workspace["id"],
        "personal_workspace_role": "editor",
        "role": "editor",
        "username": "alice",
    }


def test_registered_users_do_not_see_each_others_workspaces(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)

    client = TestClient(app)
    alice = client.post("/api/auth/register", json={"username": "alice", "password": "alice-pass"}).json()
    bob = client.post("/api/auth/register", json={"username": "bob", "password": "bob-pass-123"}).json()

    alice_workspaces = client.get(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {alice['access_token']}"},
    )
    bob_workspaces = client.get(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {bob['access_token']}"},
    )

    assert alice_workspaces.status_code == 200
    assert bob_workspaces.status_code == 200
    assert [workspace["name"] for workspace in alice_workspaces.json()] == ["alice 的工作区"]
    assert [workspace["name"] for workspace in bob_workspaces.json()] == ["bob 的工作区"]
    assert alice_workspaces.json()[0]["id"] != bob_workspaces.json()[0]["id"]

    bob_workspace_id = bob_workspaces.json()[0]["id"]
    forbidden = client.get(
        f"/api/knowledge-base/stats?workspace_id={bob_workspace_id}",
        headers={"Authorization": f"Bearer {alice['access_token']}"},
    )
    assert forbidden.status_code == 403


def test_register_rejects_duplicate_username_without_logging_password(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="alice", password_hash=hash_password("alice-pass"), role="viewer")

    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "different-pass"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "用户已存在"
    assert len([user for user in auth_store.list_users() if user["username"] == "alice"]) == 1
    audit_events = audit_store.list_events(limit=10)
    assert audit_events[0]["action"] == "auth.register_failed"
    assert audit_events[0]["target_id"] == "alice"
    assert audit_events[0]["metadata"] == {"reason": "duplicate_username", "username": "alice"}
    assert "password" not in audit_events[0]["metadata"]


def test_login_is_rate_limited_by_ip_and_username(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("pw"), role="admin")

    client = TestClient(app)
    with patch(
        "src.api.rate_limit.get_runtime_setting",
        side_effect=lambda key, default=None: 1 if key == "auth_login_rate_limit_per_minute" else default,
    ):
        first = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
        second = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})

    assert first.status_code == 401
    assert second.status_code == 429
    assert "请求过于频繁" in second.json()["detail"]
    assert int(second.headers["Retry-After"]) >= 1


def test_login_ip_rate_limit_ignores_spoofed_forwarded_for(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)

    client = TestClient(app)
    with patch(
        "src.api.rate_limit.get_runtime_setting",
        side_effect=lambda key, default=None: 1 if key == "auth_login_rate_limit_per_minute" else default,
    ):
        first = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "bad"},
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        second = client.post(
            "/api/auth/login",
            json={"username": "bob", "password": "bad"},
            headers={"X-Forwarded-For": "203.0.113.11"},
        )

    assert first.status_code == 401
    assert second.status_code == 429
    assert "请求过于频繁" in second.json()["detail"]


def test_me_requires_valid_access_token(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)

    client = TestClient(app)
    response = client.get("/api/auth/me")

    assert response.status_code == 401
