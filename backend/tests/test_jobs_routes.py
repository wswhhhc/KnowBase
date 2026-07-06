from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth_tokens import hash_password
from src.api.main import app
from src.persistence import auth_store, job_store
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url
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


def test_user_can_cancel_own_queued_job(isolated_jobs_database):
    users = _seed_users()
    editor_job = job_store.create_job(
        job_type="ingest_url",
        created_by_user_id=users["editor"]["id"],
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
