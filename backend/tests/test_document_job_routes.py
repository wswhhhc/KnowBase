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


def test_upload_returns_queued_job_without_running_kb_import():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    queued_job = _job_payload("job-upload-1")
    queued_job["job_type"] = "ingest_file"
    queued_job["workspace_id"] = "ws-a"
    uploaded_path = None
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job", return_value=queued_job) as mock_enqueue:
            with patch.object(fake_kb, "ingest_file") as mock_ingest_file:
                response = client.post(
                    "/api/documents/upload?workspace_id=ws-a&version_mode=append",
                    files={"file": ("upload.txt", b"hello", "text/plain")},
                )

        assert response.status_code == 200
        assert response.json()["job_id"] == "job-upload-1"
        assert response.json()["job"]["status"] == "queued"
        mock_ingest_file.assert_not_called()
        call_kwargs = mock_enqueue.call_args.kwargs
        uploaded_path = call_kwargs["kwargs"]["file_path"]
        assert call_kwargs["job_type"] == "ingest_file"
        assert call_kwargs["target_path"] == "src.jobs.document_tasks:ingest_file_document"
        assert call_kwargs["created_by_user_id"] is None
        assert call_kwargs["workspace_id"] == "ws-a"
        assert call_kwargs["kwargs"]["source_name"] == "upload.txt"
        assert call_kwargs["kwargs"]["version_mode"] == "append"
        assert call_kwargs["kwargs"]["workspace_id"] == "ws-a"
        assert call_kwargs["inject_job_id"] is True
    finally:
        if uploaded_path:
            from pathlib import Path
            Path(uploaded_path).unlink(missing_ok=True)
        teardown_test_env(tmp_dir, orig_db, patchers)


def test_upload_existing_source_probe_does_not_enqueue_job_and_removes_temp_file():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    try:
        with patch.object(fake_kb, "source_counts", return_value=[("upload.txt", 1)]):
            with patch("src.api.routes.documents.enqueue_tracked_job") as mock_enqueue:
                response = client.post(
                    "/api/documents/upload?workspace_id=ws-a",
                    files={"file": ("upload.txt", b"hello", "text/plain")},
                )
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    assert response.json()["existing_version"] is True
    assert response.json()["chunk_count"] == 0
    mock_enqueue.assert_not_called()


def test_ingest_url_returns_queued_job_without_running_kb_import():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job", return_value=_job_payload()) as mock_enqueue:
            with patch.object(fake_kb, "ingest_url") as mock_ingest_url:
                response = client.post(
                    "/api/documents/ingest-url?workspace_id=ws-a&version_mode=append",
                    json={"url": "https://example.com/page"},
                )
    finally:
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
    try:
        with patch.object(fake_kb, "source_counts", return_value=[("https://example.com/page", 1)]):
            with patch("src.api.routes.documents.enqueue_tracked_job") as mock_enqueue:
                response = client.post(
                    "/api/documents/ingest-url?workspace_id=ws-a",
                    json={"url": "https://example.com/page"},
                )
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    assert response.json()["existing_version"] is True
    assert response.json()["chunk_count"] == 0
    mock_enqueue.assert_not_called()
