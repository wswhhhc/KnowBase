from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import auth_store
from tests.test_auth_routes import _configure_auth_database


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _api_key_runtime_setting(key, default=None):
    if key == "api_key":
        return "test-api-key"
    return default


def _seed_admin_and_viewer(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")


def test_admin_jwt_can_read_settings_when_api_key_is_configured(monkeypatch, tmp_path):
    _seed_admin_and_viewer(monkeypatch, tmp_path)
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        with patch("src.api.routes.settings.get_public_settings", return_value={"api_key": "__KEEP_EXISTING_SECRET__"}):
            response = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["api_key"] == "__KEEP_EXISTING_SECRET__"


def test_viewer_jwt_cannot_read_settings(monkeypatch, tmp_path):
    _seed_admin_and_viewer(monkeypatch, tmp_path)
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_legacy_api_key_can_update_settings(monkeypatch, tmp_path):
    _seed_admin_and_viewer(monkeypatch, tmp_path)
    client = TestClient(app)

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        with patch("src.api.routes.settings.update_runtime_settings") as mock_update_runtime_settings:
            response = client.put(
                "/api/settings",
                json={"chunk_size": 2048},
                headers={"Authorization": "Bearer test-api-key"},
            )

    assert response.status_code == 200
    mock_update_runtime_settings.assert_called_once_with({"chunk_size": 2048})
