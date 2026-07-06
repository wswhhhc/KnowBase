from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import auth_store, workspace_store
from tests.test_auth_routes import _configure_auth_database


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_can_replace_and_list_workspace_members(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    admin = auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    editor = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    workspace = workspace_store.create_workspace("团队空间")
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")
    headers = {"Authorization": f"Bearer {token}"}

    replaced = client.put(
        f"/api/workspaces/{workspace['id']}/members",
        json={
            "members": [
                {"user_id": editor["id"], "role": "editor"},
                {"user_id": viewer["id"], "role": "viewer"},
            ]
        },
        headers=headers,
    )

    assert replaced.status_code == 200
    assert [member["username"] for member in replaced.json()] == ["editor", "viewer"]
    assert {member["role"] for member in replaced.json()} == {"editor", "viewer"}

    listed = client.get(f"/api/workspaces/{workspace['id']}/members", headers=headers)

    assert listed.status_code == 200
    assert listed.json() == replaced.json()
    assert admin["id"] not in {member["user_id"] for member in listed.json()}


def test_viewer_cannot_manage_workspace_members(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    workspace = workspace_store.create_workspace("团队空间")
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    response = client.get(
        f"/api/workspaces/{workspace['id']}/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_jwt_can_manage_members_when_api_key_is_configured(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    workspace = workspace_store.create_workspace("团队空间")
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")

    with patch("src.api.deps.get_runtime_setting", return_value="test-api-key"):
        response = client.get(
            f"/api/workspaces/{workspace['id']}/members",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


def test_replace_workspace_members_rejects_duplicate_users(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    editor = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    workspace = workspace_store.create_workspace("团队空间")
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")

    response = client.put(
        f"/api/workspaces/{workspace['id']}/members",
        json={
            "members": [
                {"user_id": editor["id"], "role": "editor"},
                {"user_id": editor["id"], "role": "viewer"},
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_replace_workspace_members_rejects_unknown_workspace(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")

    response = client.put(
        "/api/workspaces/missing/members",
        json={"members": []},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
