from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import auth_store
from tests.test_auth_routes import _configure_auth_database


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_can_create_list_update_and_delete_users(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")
    headers = {"Authorization": f"Bearer {admin_token}"}

    created = client.post(
        "/api/admin/users",
        json={"username": "viewer", "password": "viewer-pass", "role": "viewer"},
        headers=headers,
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["username"] == "viewer"
    assert "password_hash" not in created_body

    listed = client.get("/api/admin/users", headers=headers)
    assert listed.status_code == 200
    assert {user["username"] for user in listed.json()} == {"admin", "viewer"}

    updated = client.patch(
        f"/api/admin/users/{created_body['id']}",
        json={"role": "editor", "is_active": False},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "editor"
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/admin/users/{created_body['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}


def test_viewer_cannot_manage_users(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    client = TestClient(app)
    viewer_token = _login(client, "viewer", "viewer-pass")

    response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 403


def test_admin_create_user_rejects_short_password(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")

    response = client.post(
        "/api/admin/users",
        json={"username": "bad", "password": "short", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422
