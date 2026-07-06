from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.deps import get_knowledge_base
from src.api.main import app
from src.persistence import auth_store
from tests.helpers import FakeKnowledgeBase
from tests.test_auth_routes import _configure_auth_database


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _api_key_runtime_setting(key, default=None):
    if key == "api_key":
        return "test-api-key"
    return default


def _seed_users_and_workspace(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    auth_store.create_user(username="outsider", password_hash=hash_password("outsider-pass"), role="viewer")
    workspace_id = "ws-chat"
    auth_store.replace_workspace_members(
        workspace_id=workspace_id,
        members=[{"user_id": viewer["id"], "role": "viewer"}],
    )
    return workspace_id


def _chat_body(workspace_id: str) -> dict:
    return {
        "question": "测试问题",
        "web_search_enabled": False,
        "search_strategy": "balanced",
        "workspace_id": workspace_id,
    }


def _successful_run_query(**kwargs):
    yield ("updates", {"finalize": {"evidence_level": "low", "outcome_category": "success"}})


def test_workspace_viewer_can_chat_with_jwt_when_api_key_is_configured(monkeypatch, tmp_path):
    workspace_id = _seed_users_and_workspace(monkeypatch, tmp_path)
    app.dependency_overrides[get_knowledge_base] = lambda: FakeKnowledgeBase()
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            with patch("src.api.chat_stream_service.run_query", side_effect=_successful_run_query):
                response = client.post(
                    "/api/chat/stream",
                    json=_chat_body(workspace_id),
                    headers={"Authorization": f"Bearer {token}"},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_workspace_non_member_cannot_chat(monkeypatch, tmp_path):
    workspace_id = _seed_users_and_workspace(monkeypatch, tmp_path)
    app.dependency_overrides[get_knowledge_base] = lambda: FakeKnowledgeBase()
    client = TestClient(app)
    token = _login(client, "outsider", "outsider-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.post(
                "/api/chat/stream",
                json=_chat_body(workspace_id),
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_legacy_api_key_can_still_chat(monkeypatch, tmp_path):
    workspace_id = _seed_users_and_workspace(monkeypatch, tmp_path)
    app.dependency_overrides[get_knowledge_base] = lambda: FakeKnowledgeBase()
    client = TestClient(app)

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            with patch("src.api.chat_stream_service.run_query", side_effect=_successful_run_query):
                response = client.post(
                    "/api/chat/stream",
                    json=_chat_body(workspace_id),
                    headers={"Authorization": "Bearer test-api-key"},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
