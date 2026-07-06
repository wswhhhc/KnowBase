from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import auth_store, bookmark_store
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
    init_temp_database(tmp_path / "bookmarks.db")
    yield
    teardown_temp_database()


def _seed_users() -> None:
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    editor = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    auth_store.create_user(username="outsider", password_hash=hash_password("outsider-pass"), role="viewer")
    auth_store.replace_workspace_members(
        workspace_id="ws-alpha",
        members=[
            {"user_id": viewer["id"], "role": "viewer"},
            {"user_id": editor["id"], "role": "editor"},
        ],
    )


def test_viewer_lists_only_authorized_workspace_bookmarks(isolated_databases):
    _seed_users()
    bookmark_store.create_bookmark(workspace_id="ws-alpha", content="Alpha")
    bookmark_store.create_bookmark(workspace_id="ws-beta", content="Beta")
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            "/api/bookmarks?workspace_id=ws-alpha",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert [bookmark["content"] for bookmark in response.json()] == ["Alpha"]


def test_viewer_cannot_create_bookmark_in_authorized_workspace(isolated_databases):
    _seed_users()
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            "/api/bookmarks",
            json={"workspace_id": "ws-alpha", "content": "Alpha"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


def test_editor_cannot_update_bookmark_in_unauthorized_workspace(isolated_databases):
    _seed_users()
    bookmark = bookmark_store.create_bookmark(workspace_id="ws-beta", note="old")
    client = TestClient(app)
    token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.patch(
            f"/api/bookmarks/{bookmark['id']}",
            json={"note": "new"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert bookmark_store.get_bookmark(bookmark["id"])["note"] == "old"


def test_editor_deletes_bookmark_in_authorized_workspace(isolated_databases):
    _seed_users()
    bookmark = bookmark_store.create_bookmark(workspace_id="ws-alpha", note="old")
    client = TestClient(app)
    token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.delete(
            f"/api/bookmarks/{bookmark['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert bookmark_store.get_bookmark(bookmark["id"]) is None


def test_legacy_api_key_keeps_unscoped_bookmark_list_behavior(isolated_databases):
    _seed_users()
    bookmark_store.create_bookmark(workspace_id="ws-alpha", content="Alpha")
    bookmark_store.create_bookmark(workspace_id="ws-beta", content="Beta")
    client = TestClient(app)

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            "/api/bookmarks",
            headers={"Authorization": "Bearer test-api-key"},
        )

    assert response.status_code == 200
    assert {bookmark["content"] for bookmark in response.json()} == {"Alpha", "Beta"}
