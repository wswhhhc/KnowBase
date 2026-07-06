from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import auth_store, conversation_store
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
    init_temp_database(tmp_path / "conversations.db")
    yield
    teardown_temp_database()


def _seed_users() -> None:
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    auth_store.create_user(username="outsider", password_hash=hash_password("outsider-pass"), role="viewer")
    auth_store.replace_workspace_members(
        workspace_id="ws-alpha",
        members=[{"user_id": viewer["id"], "role": "viewer"}],
    )


def test_viewer_lists_only_authorized_workspace_conversations(isolated_databases):
    _seed_users()
    conversation_store.create_conversation("Alpha", workspace_id="ws-alpha")
    conversation_store.create_conversation("Beta", workspace_id="ws-beta")
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            "/api/conversations?workspace_id=ws-alpha",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert [conversation["title"] for conversation in response.json()] == ["Alpha"]


def test_viewer_can_read_authorized_conversation_without_workspace_query(isolated_databases):
    _seed_users()
    conversation = conversation_store.create_conversation("Alpha", workspace_id="ws-alpha")
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            f"/api/conversations/{conversation['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == conversation["id"]
    assert response.json()["title"] == "Alpha"


def test_viewer_cannot_read_unauthorized_conversation_by_id(isolated_databases):
    _seed_users()
    conversation = conversation_store.create_conversation("Beta", workspace_id="ws-beta")
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            f"/api/conversations/{conversation['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


def test_viewer_cannot_create_conversation_in_unauthorized_workspace(isolated_databases):
    _seed_users()
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            "/api/conversations?workspace_id=ws-beta",
            json={"title": "Beta"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


def test_legacy_api_key_keeps_unscoped_conversation_list_behavior(isolated_databases):
    _seed_users()
    conversation_store.create_conversation("Default", workspace_id="")
    conversation_store.create_conversation("Alpha", workspace_id="ws-alpha")
    client = TestClient(app)

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            "/api/conversations",
            headers={"Authorization": "Bearer test-api-key"},
        )

    assert response.status_code == 200
    assert {conversation["title"] for conversation in response.json()} == {"Default", "Alpha"}
