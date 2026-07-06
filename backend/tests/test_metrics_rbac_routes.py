from __future__ import annotations

from unittest.mock import patch

import pytest
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


@pytest.fixture()
def auth_database(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)


def _seed_users() -> None:
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")


def test_admin_can_read_metrics_logs_with_jwt(auth_database):
    _seed_users()
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")

    with (
        patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting),
        patch("src.api.routes.metrics._load_query_logs", return_value=[]),
    ):
        response = client.get("/api/metrics/logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["logs"] == []


def test_viewer_cannot_read_metrics_logs(auth_database):
    _seed_users()
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get("/api/metrics/logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_legacy_api_key_can_read_metrics_logs(auth_database):
    _seed_users()
    client = TestClient(app)

    with (
        patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting),
        patch("src.api.routes.metrics._load_query_logs", return_value=[]),
    ):
        response = client.get("/api/metrics/logs", headers={"Authorization": "Bearer test-api-key"})

    assert response.status_code == 200
    assert response.json()["logs"] == []
