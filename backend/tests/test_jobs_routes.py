from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.jobs.tasks import run_tracked_job
from src.persistence import audit_store, auth_store, job_store
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url
from src.utils import UPLOAD_TEMP_DIR
from tests.test_auth_routes import _configure_auth_database


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _api_key_runtime_setting(key, default=None):
    if key == "api_key":
        return "test-api-key"
    return default


class FakeQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, func, *args, **kwargs):
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})
        return None


@pytest.fixture()
def isolated_jobs_database(monkeypatch, tmp_path):
    database_url = _configure_auth_database(monkeypatch, tmp_path)
    engine = create_engine_for_url(database_url)
    metadata.create_all(engine)
    yield


def _seed_users() -> dict[str, dict]:
    admin = auth_store.create_user(username="admin", password_hash=hash_password("admin-pass"), role="admin")
    editor = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    viewer = auth_store.create_user(username="viewer", password_hash=hash_password("viewer-pass"), role="viewer")
    return {"admin": admin, "editor": editor, "viewer": viewer}


def test_admin_lists_all_jobs_and_user_lists_only_own_jobs(isolated_jobs_database):
    users = _seed_users()
    auth_store.replace_workspace_members(
        workspace_id="ws-a",
        members=[{"user_id": users["editor"]["id"], "role": "viewer"}],
    )
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
    )
    viewer_job = job_store.create_job(
        job_type="ingest_file",
        created_by_user_id=users["viewer"]["id"],
        workspace_id="ws-b",
    )
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        admin_response = client.get("/api/jobs", headers={"Authorization": f"Bearer {admin_token}"})
        editor_response = client.get("/api/jobs", headers={"Authorization": f"Bearer {editor_token}"})

    assert admin_response.status_code == 200
    assert {job["id"] for job in admin_response.json()} == {editor_job["id"], viewer_job["id"]}
    assert editor_response.status_code == 200
    assert [job["id"] for job in editor_response.json()] == [editor_job["id"]]


def test_user_job_list_hides_workspace_jobs_without_current_access(isolated_jobs_database):
    users = _seed_users()
    accessible_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="",
    )
    hidden_job = job_store.create_job(
        job_type="clear_workspace",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get("/api/jobs", headers={"Authorization": f"Bearer {editor_token}"})

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [accessible_job["id"]]
    assert hidden_job["id"] not in {job["id"] for job in response.json()}


def test_jobs_require_auth_when_api_key_configured(isolated_jobs_database):
    _seed_users()
    client = TestClient(app)

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get("/api/jobs")

    assert response.status_code == 401


def test_legacy_api_key_lists_all_jobs(isolated_jobs_database):
    users = _seed_users()
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
    )
    viewer_job = job_store.create_job(
        job_type="ingest_file",
        created_by_user_id=users["viewer"]["id"],
    )
    client = TestClient(app)

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get("/api/jobs", headers={"Authorization": "Bearer test-api-key"})

    assert response.status_code == 200
    assert {job["id"] for job in response.json()} == {editor_job["id"], viewer_job["id"]}


def test_user_cannot_get_another_users_job(isolated_jobs_database):
    users = _seed_users()
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
    )
    client = TestClient(app)
    viewer_token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            f"/api/jobs/{editor_job['id']}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert response.status_code == 404


def test_user_cannot_get_own_workspace_job_without_current_access(isolated_jobs_database):
    users = _seed_users()
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.get(
            f"/api/jobs/{editor_job['id']}",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 403


def test_user_can_cancel_own_queued_job(isolated_jobs_database):
    users = _seed_users()
    auth_store.replace_workspace_members(
        workspace_id="ws-a",
        members=[{"user_id": users["editor"]["id"], "role": "editor"}],
    )
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            f"/api/jobs/{editor_job['id']}/cancel",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert response.json()["finished_at"] is not None
    audit_events = audit_store.list_events(actor_user_id=users["editor"]["id"])
    cancel_event = next(event for event in audit_events if event["action"] == "job.canceled")
    assert cancel_event["target_id"] == editor_job["id"]
    assert cancel_event["metadata"] == {"job_type": "ingest_url", "workspace_id": "ws-a"}


def test_cancel_already_canceled_job_is_idempotent_without_duplicate_audit(isolated_jobs_database):
    users = _seed_users()
    auth_store.replace_workspace_members(
        workspace_id="ws-a",
        members=[{"user_id": users["editor"]["id"], "role": "editor"}],
    )
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        first_response = client.post(
            f"/api/jobs/{editor_job['id']}/cancel",
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        second_response = client.post(
            f"/api/jobs/{editor_job['id']}/cancel",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["status"] == "canceled"
    audit_events = audit_store.list_events(actor_user_id=users["editor"]["id"])
    cancel_events = [event for event in audit_events if event["action"] == "job.canceled"]
    assert [event["target_id"] for event in cancel_events] == [editor_job["id"]]


def test_cancel_queued_file_upload_job_removes_upload_temp_file(isolated_jobs_database):
    users = _seed_users()
    auth_store.replace_workspace_members(
        workspace_id="ws-a",
        members=[{"user_id": users["editor"]["id"], "role": "editor"}],
    )
    upload_dir = UPLOAD_TEMP_DIR
    upload_dir.mkdir(exist_ok=True)
    upload_path = upload_dir / "queued-cancel-upload.txt"
    upload_path.write_text("pending upload", encoding="utf-8")
    editor_job = job_store.create_job(
        job_type="ingest_file",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
        progress={
            "_retry": {
                "target_path": "src.jobs.document_tasks:ingest_file_document",
                "kwargs": {"file_path": str(upload_path)},
            }
        },
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            f"/api/jobs/{editor_job['id']}/cancel",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert not upload_path.exists()


def test_cancel_file_upload_job_does_not_remove_paths_outside_upload_temp(isolated_jobs_database, tmp_path):
    users = _seed_users()
    auth_store.replace_workspace_members(
        workspace_id="ws-a",
        members=[{"user_id": users["editor"]["id"], "role": "editor"}],
    )
    unrelated_path = tmp_path / "must-stay.txt"
    unrelated_path.write_text("not an upload temp file", encoding="utf-8")
    editor_job = job_store.create_job(
        job_type="ingest_file",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
        progress={
            "_retry": {
                "target_path": "src.jobs.document_tasks:ingest_file_document",
                "kwargs": {"file_path": str(unrelated_path)},
            }
        },
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            f"/api/jobs/{editor_job['id']}/cancel",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 200
    assert unrelated_path.exists()


def test_cancel_finished_job_returns_conflict(isolated_jobs_database):
    users = _seed_users()
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        status="succeeded",
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            f"/api/jobs/{editor_job['id']}/cancel",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 409


def test_user_cannot_cancel_own_workspace_job_without_current_editor_role(isolated_jobs_database):
    users = _seed_users()
    editor_job = job_store.create_job(
        job_type="clear_workspace",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            f"/api/jobs/{editor_job['id']}/cancel",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 403
    assert job_store.get_job(editor_job["id"])["status"] == "queued"


def test_user_can_retry_own_failed_url_job(isolated_jobs_database):
    users = _seed_users()
    auth_store.replace_workspace_members(
        workspace_id="ws-a",
        members=[{"user_id": users["editor"]["id"], "role": "editor"}],
    )
    failed_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
        status="failed",
        progress={
            "phase": "fetching",
            "percent": 25,
            "message": "URL 下载失败",
            "_retry": {
                "target_path": "src.jobs.document_tasks:ingest_url_document",
                "args": [],
                "kwargs": {"url": "https://example.com/doc", "version_mode": "replace", "workspace_id": "ws-a"},
                "inject_job_id": True,
            },
        },
    )
    fake_queue = FakeQueue()
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        with patch("src.jobs.enqueue.create_queue", return_value=fake_queue):
            response = client.post(
                f"/api/jobs/{failed_job['id']}/retry",
                headers={"Authorization": f"Bearer {editor_token}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["error"] == ""
    assert body["progress"] == {"phase": "queued", "percent": 0, "message": "任务已重新排队"}
    assert fake_queue.calls[0]["func"] is run_tracked_job
    assert fake_queue.calls[0]["args"] == (
        failed_job["id"],
        "src.jobs.document_tasks:ingest_url_document",
        [],
        {
            "url": "https://example.com/doc",
            "version_mode": "replace",
            "workspace_id": "ws-a",
            "job_id": failed_job["id"],
        },
    )


def test_admin_retry_records_admin_as_audit_actor(isolated_jobs_database):
    users = _seed_users()
    failed_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
        status="failed",
        progress={
            "_retry": {
                "target_path": "src.jobs.document_tasks:ingest_url_document",
                "args": [],
                "kwargs": {"url": "https://example.com/doc", "version_mode": "replace", "workspace_id": "ws-a"},
                "inject_job_id": True,
            }
        },
    )
    fake_queue = FakeQueue()
    client = TestClient(app)
    admin_token = _login(client, "admin", "admin-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        with patch("src.jobs.enqueue.create_queue", return_value=fake_queue):
            response = client.post(
                f"/api/jobs/{failed_job['id']}/retry",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

    assert response.status_code == 200
    admin_events = audit_store.list_events(actor_user_id=users["admin"]["id"])
    retry_event = next(event for event in admin_events if event["action"] == "job.retried")
    assert retry_event["target_id"] == failed_job["id"]
    editor_events = audit_store.list_events(actor_user_id=users["editor"]["id"])
    assert not [event for event in editor_events if event["action"] == "job.retried"]


def test_user_cannot_retry_own_job_without_current_workspace_editor_role(isolated_jobs_database):
    users = _seed_users()
    failed_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
        status="failed",
        progress={
            "_retry": {
                "target_path": "src.jobs.document_tasks:ingest_url_document",
                "args": [],
                "kwargs": {"url": "https://example.com/doc", "version_mode": "replace", "workspace_id": "ws-a"},
            }
        },
    )
    fake_queue = FakeQueue()
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        with patch("src.jobs.enqueue.create_queue", return_value=fake_queue):
            response = client.post(
                f"/api/jobs/{failed_job['id']}/retry",
                headers={"Authorization": f"Bearer {editor_token}"},
            )

    assert response.status_code == 403
    assert fake_queue.calls == []


def test_user_cannot_retry_another_users_job(isolated_jobs_database):
    users = _seed_users()
    failed_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
        status="failed",
        progress={"_retry": {"target_path": "tests.test_job_tasks:sample_task", "args": [1, 2], "kwargs": {}}},
    )
    client = TestClient(app)
    viewer_token = _login(client, "viewer", "viewer-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            f"/api/jobs/{failed_job['id']}/retry",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert response.status_code == 404


def test_get_succeeded_kb_mutation_job_invalidates_knowledge_base_cache(isolated_jobs_database):
    users = _seed_users()
    auth_store.replace_workspace_members(
        workspace_id="ws-a",
        members=[{"user_id": users["editor"]["id"], "role": "viewer"}],
    )
    job = job_store.create_job(
        job_type="ingest_file",
        created_by_user_id=users["editor"]["id"],
        workspace_id="ws-a",
        status="succeeded",
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        with patch("src.api.routes.jobs.get_knowledge_base.cache_clear") as mock_cache_clear:
            response = client.get(
                f"/api/jobs/{job['id']}",
                headers={"Authorization": f"Bearer {editor_token}"},
            )

    assert response.status_code == 200
    mock_cache_clear.assert_called_once()


def test_retry_file_upload_job_returns_conflict(isolated_jobs_database):
    users = _seed_users()
    failed_job = job_store.create_job(
        job_type="ingest_file",
        created_by_user_id=users["editor"]["id"],
        status="failed",
        progress={"_retry": {"target_path": "src.jobs.document_tasks:ingest_file_document", "args": [], "kwargs": {}}},
    )
    client = TestClient(app)
    editor_token = _login(client, "editor", "editor-pass")

    with patch("src.api.deps.get_runtime_setting", side_effect=_api_key_runtime_setting):
        response = client.post(
            f"/api/jobs/{failed_job['id']}/retry",
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 409
    assert "重新上传文件" in response.json()["detail"]
