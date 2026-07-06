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


def test_admin_can_list_and_filter_audit_logs(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    admin = auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    editor = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    audit_store.record_event(
        action="job.queued",
        actor_user_id=editor["id"],
        target_type="job",
        target_id="job-1",
        metadata={"job_type": "ingest_url", "workspace_id": "ws-a"},
    )
    audit_store.record_event(
        action="auth.login_succeeded",
        actor_user_id=admin["id"],
        target_type="user",
        target_id=admin["id"],
        metadata={"username": "admin"},
    )
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")

    response = client.get(
        f"/api/admin/audit-logs?actor_user_id={editor['id']}&limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "actor_user_id": editor["id"],
            "action": "job.queued",
            "target_type": "job",
            "target_id": "job-1",
            "metadata": {"job_type": "ingest_url", "workspace_id": "ws-a"},
            "created_at": response.json()[0]["created_at"],
        }
    ]


def test_viewer_cannot_list_audit_logs(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    client = TestClient(app)
    viewer_token = _login(client, "viewer", "viewer-pass")

    response = client.get("/api/admin/audit-logs", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 403
