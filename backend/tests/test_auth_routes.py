from __future__ import annotations

from fastapi.testclient import TestClient
from unittest.mock import patch

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import audit_store, auth_store
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def _configure_auth_database(monkeypatch, tmp_path):
    database_url = f"sqlite:///{tmp_path / 'auth.db'}"
    engine = create_engine_for_url(database_url)
    metadata.create_all(engine)
    monkeypatch.setattr(auth_store.settings, "database_url", database_url)
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
