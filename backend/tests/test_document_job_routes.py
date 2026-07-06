from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from tests.helpers import setup_test_env, teardown_test_env


def _job_payload(job_id: str = "job-url-1") -> dict:
    return {
        "id": job_id,
        "job_type": "ingest_url",
        "status": "queued",
        "created_by_user_id": None,
        "workspace_id": "ws-a",
        "progress": {"phase": "queued", "percent": 0},
        "error": "",
        "attempts": 0,
        "created_at": "2026-07-06T00:00:00+00:00",
        "updated_at": "2026-07-06T00:00:00+00:00",
        "started_at": None,
        "finished_at": None,
    }


def test_ingest_url_returns_queued_job_without_running_kb_import():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    with patch("src.api.routes.documents.enqueue_tracked_job", return_value=_job_payload()) as mock_enqueue:
        with patch.object(fake_kb, "ingest_url") as mock_ingest_url:
            response = client.post(
                "/api/documents/ingest-url?workspace_id=ws-a&version_mode=append",
                json={"url": "https://example.com/page"},
            )
    teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-url-1"
    assert response.json()["job"]["status"] == "queued"
    assert response.json()["job"]["progress"] == {"phase": "queued", "percent": 0, "message": ""}
    mock_ingest_url.assert_not_called()
    mock_enqueue.assert_called_once_with(
        job_type="ingest_url",
        target_path="src.jobs.document_tasks:ingest_url_document",
        created_by_user_id=None,
        workspace_id="ws-a",
        kwargs={
            "url": "https://example.com/page",
            "version_mode": "append",
            "workspace_id": "ws-a",
        },
        inject_job_id=True,
    )


def test_ingest_url_existing_source_probe_does_not_enqueue_job():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    with patch.object(fake_kb, "source_counts", return_value=[("https://example.com/page", 1)]):
        with patch("src.api.routes.documents.enqueue_tracked_job") as mock_enqueue:
            response = client.post(
                "/api/documents/ingest-url?workspace_id=ws-a",
                json={"url": "https://example.com/page"},
            )
    teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    assert response.json()["existing_version"] is True
    assert response.json()["chunk_count"] == 0
    mock_enqueue.assert_not_called()
