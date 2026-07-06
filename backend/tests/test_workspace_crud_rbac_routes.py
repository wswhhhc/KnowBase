from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import auth_store, workspace_store
from tests.helpers import init_temp_database, teardown_temp_database
from tests.test_auth_routes import _configure_auth_database


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _api_key_runtime_setting(key, default=None):
    if key == "api_key":
        return "test-api-key"
    return default


@pytest.fixture()
def isolated_databases(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    init_temp_database(tmp_path / "workspaces.db")
    yield
    teardown_temp_database()


def _seed_users() -> dict[str, dict]:
    admin = auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    editor = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    return {"admin": admin, "editor": editor, "viewer": viewer}


def test_viewer_lists_only_joined_workspaces(isolated_databases):
    users = _seed_users()
    alpha = workspace_store.create_workspace("Alpha")
    workspace_store.create_workspace("Beta")
    auth_store.replace_workspace_members(
        workspace_id=alpha["id"],
        members=[{"user_id": users["viewer"]["id"], "role": "viewer"}],
    )
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get("/api/workspaces", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [workspace["id"] for workspace in response.json()] == [alpha["id"]]


def test_editor_cannot_create_workspace(isolated_databases):
    _seed_users()
    client = TestClient(app)
    token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            "/api/workspaces",
            json={"name": "Editor Space"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


def test_admin_can_create_workspace(isolated_databases):
    _seed_users()
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            "/api/workspaces",
            json={"name": "Admin Space"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Admin Space"


def test_legacy_api_key_keeps_unscoped_workspace_list_behavior(isolated_databases):
    _seed_users()
    workspace_store.create_workspace("Alpha")
    workspace_store.create_workspace("Beta")
    client = TestClient(app)

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            "/api/workspaces",
            headers={"Authorization": "Bearer test-api-key"},
        )

    assert response.status_code == 200
    assert {workspace["name"] for workspace in response.json()} >= {"默认工作区", "Alpha", "Beta"}
