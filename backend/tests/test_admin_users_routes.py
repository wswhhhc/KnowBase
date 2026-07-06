from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import audit_store, auth_store
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

    audit_events = audit_store.list_events(actor_user_id=auth_store.get_user_by_username("admin")["id"], limit=10)
    admin_events = [event for event in audit_events if event["action"].startswith("admin.user_")]
    assert [event["action"] for event in admin_events] == [
        "admin.user_deleted",
        "admin.user_updated",
        "admin.user_created",
    ]
    assert admin_events[0]["target_type"] == "user"
    assert admin_events[0]["target_id"] == created_body["id"]
    assert admin_events[0]["metadata"] == {"username": "viewer", "role": "editor", "is_active": False}
    assert admin_events[1]["metadata"] == {
        "username": "viewer",
        "changed_fields": ["is_active", "role"],
    }
    assert admin_events[2]["metadata"] == {"username": "viewer", "role": "viewer", "is_active": True}


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


def test_admin_create_user_rejects_blank_username(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")

    response = client.post(
        "/api/admin/users",
        json={"username": "   ", "password": "viewer-pass", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422


def test_admin_create_and_update_user_trim_username(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")
    headers = {"Authorization": f"Bearer {admin_token}"}

    created = client.post(
        "/api/admin/users",
        json={"username": "  viewer  ", "password": "viewer-pass", "role": "viewer"},
        headers=headers,
    )
    assert created.status_code == 200
    assert created.json()["username"] == "viewer"

    updated = client.patch(
        f"/api/admin/users/{created.json()['id']}",
        json={"username": "  editor  "},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["username"] == "editor"
    assert auth_store.get_user_by_id(created.json()["id"])["username"] == "editor"


def test_admin_update_user_rejects_duplicate_username(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")

    response = client.patch(
        f"/api/admin/users/{viewer['id']}",
        json={"username": "editor"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "用户已存在或数据冲突"
    assert auth_store.get_user_by_id(viewer["id"])["username"] == "viewer"


def test_last_active_admin_cannot_be_disabled_demoted_or_deleted(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    admin = auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")
    headers = {"Authorization": f"Bearer {admin_token}"}

    disable = client.patch(f"/api/admin/users/{admin['id']}", json={"is_active": False}, headers=headers)
    demote = client.patch(f"/api/admin/users/{admin['id']}", json={"role": "viewer"}, headers=headers)
    delete = client.delete(f"/api/admin/users/{admin['id']}", headers=headers)

    assert disable.status_code == 409
    assert demote.status_code == 409
    assert delete.status_code == 409
    stored = auth_store.get_user_by_id(admin["id"])
    assert stored is not None
    assert stored["role"] == "admin"
    assert stored["is_active"] is True


def test_admin_password_update_revokes_existing_refresh_tokens(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")
    viewer_login = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer-pass"})
    assert viewer_login.status_code == 200
    refresh_token = viewer_login.json()["refresh_token"]

    updated = client.patch(
        f"/api/admin/users/{viewer['id']}",
        json={"password": "new-viewer-pass"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    refresh = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})

    assert updated.status_code == 200
    assert refresh.status_code == 401
