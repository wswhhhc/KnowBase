from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.deps import get_knowledge_base
from src.api.main import app
from src.persistence import audit_store, auth_store, workspace_store
from tests.test_auth_routes import _configure_auth_database


class _RbacFakeKnowledgeBase:
    def __init__(self):
        self.deleted: list[tuple[str, str]] = []

    def source_counts(self, workspace_id: str | None = None):
        return [("alpha.txt", 1)]

    def delete_source(self, source_name: str, workspace_id: str = ""):
        self.deleted.append((source_name, workspace_id))
        return 1

    def document_count_for_workspace(self, workspace_id: str = ""):
        return 0

    def import_demo_documents(self, workspace_id: str = ""):
        return 2, ["demo-a.md", "demo-b.md"]

    def list_chunks(self, *, workspace_id: str = "", source: str = "", limit: int = 1000):
        return 0, []


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
    admin = auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    editor = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    outsider = auth_store.create_user(username="outsider", password_hash=hash_password("outsider-pass"), role="viewer")
    workspace = workspace_store.create_workspace("团队空间")
    auth_store.replace_workspace_members(
        workspace_id=workspace["id"],
        members=[
            {"user_id": editor["id"], "role": "editor"},
            {"user_id": viewer["id"], "role": "viewer"},
        ],
    )
    return admin, editor, viewer, outsider, workspace


def test_viewer_member_can_read_workspace_with_jwt_when_api_key_is_configured(monkeypatch, tmp_path):
    _admin, _editor, _viewer, _outsider, workspace = _seed_users_and_workspace(monkeypatch, tmp_path)
    fake_kb = _RbacFakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.get(
                f"/api/documents/sources?workspace_id={workspace['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [{"source": "alpha.txt", "count": 1}]


def test_viewer_member_cannot_delete_workspace_source(monkeypatch, tmp_path):
    _admin, _editor, _viewer, _outsider, workspace = _seed_users_and_workspace(monkeypatch, tmp_path)
    fake_kb = _RbacFakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
    client = TestClient(app)
    token = _login(client, "viewer", "viewer-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.delete(
                f"/api/documents/source/alpha.txt?workspace_id={workspace['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert fake_kb.deleted == []


def test_editor_member_can_delete_workspace_source(monkeypatch, tmp_path):
    _admin, _editor, _viewer, _outsider, workspace = _seed_users_and_workspace(monkeypatch, tmp_path)
    fake_kb = _RbacFakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
    client = TestClient(app)
    token = _login(client, "editor", "editor-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.delete(
                f"/api/documents/source/alpha.txt?workspace_id={workspace['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_kb.deleted == [("alpha.txt", workspace["id"])]
    audit_events = audit_store.list_events(actor_user_id=_editor["id"])
    delete_event = next(event for event in audit_events if event["action"] == "document.source_deleted")
    assert delete_event["target_type"] == "source"
    assert delete_event["target_id"] == "alpha.txt"
    assert delete_event["metadata"] == {
        "workspace_id": workspace["id"],
        "source_name": "alpha.txt",
        "removed_chunks": 1,
    }


def test_editor_member_import_demo_writes_audit_event(monkeypatch, tmp_path):
    _admin, editor, _viewer, _outsider, workspace = _seed_users_and_workspace(monkeypatch, tmp_path)
    fake_kb = _RbacFakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
    client = TestClient(app)
    token = _login(client, "editor", "editor-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.post(
                f"/api/documents/import-demo?workspace_id={workspace['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    audit_events = audit_store.list_events(actor_user_id=editor["id"])
    import_event = next(event for event in audit_events if event["action"] == "document.demo_imported")
    assert import_event["target_type"] == "workspace"
    assert import_event["target_id"] == workspace["id"]
    assert import_event["metadata"] == {
        "workspace_id": workspace["id"],
        "imported_sources": ["demo-a.md", "demo-b.md"],
        "chunk_count": 2,
    }


def test_workspace_non_member_is_rejected(monkeypatch, tmp_path):
    _admin, _editor, _viewer, _outsider, workspace = _seed_users_and_workspace(monkeypatch, tmp_path)
    fake_kb = _RbacFakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
    client = TestClient(app)
    token = _login(client, "outsider", "outsider-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.get(
                f"/api/documents/sources?workspace_id={workspace['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_can_write_any_workspace_without_membership(monkeypatch, tmp_path):
    _admin, _editor, _viewer, _outsider, workspace = _seed_users_and_workspace(monkeypatch, tmp_path)
    fake_kb = _RbacFakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
    client = TestClient(app)
    token = _login(client, "admin", "admin-pass")

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.delete(
                f"/api/documents/source/alpha.txt?workspace_id={workspace['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_kb.deleted == [("alpha.txt", workspace["id"])]


def test_legacy_api_key_still_allows_workspace_document_routes(monkeypatch, tmp_path):
    _admin, _editor, _viewer, _outsider, workspace = _seed_users_and_workspace(monkeypatch, tmp_path)
    fake_kb = _RbacFakeKnowledgeBase()
    app.dependency_overrides[get_knowledge_base] = lambda: fake_kb
    client = TestClient(app)

    try:
        with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
            response = client.delete(
                f"/api/documents/source/alpha.txt?workspace_id={workspace['id']}",
                headers={"Authorization": "Bearer test-api-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_kb.deleted == [("alpha.txt", workspace["id"])]
