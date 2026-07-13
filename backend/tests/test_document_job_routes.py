from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.helpers import setup_test_env, teardown_test_env


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    current_event = "message"
    for line in text.splitlines():
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            events.append({"event": current_event, "data": json.loads(line[6:])})
            current_event = "message"
    return events


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
            with patch("src.api.routes.documents.audit_store.record_event") as mock_audit:
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
        mock_audit.assert_called_once()
        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["action"] == "document.file_import_queued"
        assert audit_kwargs["target_type"] == "job"
        assert audit_kwargs["target_id"] == "job-upload-1"
        assert audit_kwargs["metadata"] == {
            "workspace_id": "ws-a",
            "job_type": "ingest_file",
            "version_mode": "append",
            "stream": False,
            "source_name": "upload.txt",
        }
        assert Path(uploaded_path).exists()
    finally:
        if uploaded_path:
            Path(uploaded_path).unlink(missing_ok=True)
        teardown_test_env(tmp_dir, orig_db, patchers)


def test_upload_existing_source_probe_does_not_enqueue_job_and_removes_temp_file(tmp_path):
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    upload_path = tmp_path / "upload.txt"
    upload_path.write_bytes(b"hello")
    try:
        with patch("src.api.routes.documents.save_uploaded_file", return_value=(str(upload_path), "upload.txt")):
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
    assert not upload_path.exists()
    mock_enqueue.assert_not_called()


def test_upload_enqueue_failure_removes_route_owned_temp_file(tmp_path):
    _fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    upload_path = tmp_path / "upload.txt"
    upload_path.write_bytes(b"hello")
    try:
        with patch("src.api.routes.documents.save_uploaded_file", return_value=(str(upload_path), "upload.txt")):
            with patch("src.api.routes.documents.enqueue_tracked_job", side_effect=RuntimeError("queue down")):
                response = client.post(
                    "/api/documents/upload?workspace_id=ws-a",
                    files={"file": ("upload.txt", b"hello", "text/plain")},
                )
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 503
    assert not upload_path.exists()


@pytest.mark.parametrize("endpoint", ["upload", "upload-stream"])
def test_upload_validation_failure_removes_route_owned_temp_file(tmp_path, endpoint):
    _fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    upload_path = tmp_path / "upload.txt"
    upload_path.write_bytes(b"hello")
    try:
        with patch("src.api.routes.documents.save_uploaded_file", return_value=(str(upload_path), "upload.txt")):
            with patch("src.api.routes.documents.submit_file_import", side_effect=ValueError("invalid source")):
                response = client.post(
                    f"/api/documents/{endpoint}?workspace_id=ws-a",
                    files={"file": ("upload.txt", b"hello", "text/plain")},
                )
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 400
    assert not upload_path.exists()


@pytest.mark.parametrize("endpoint", ["upload", "upload-stream"])
def test_queued_upload_audit_failure_does_not_delete_worker_owned_temp_file(tmp_path, endpoint):
    _fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    queued_job = _job_payload(f"job-{endpoint}")
    queued_job["job_type"] = "ingest_file"
    upload_path = tmp_path / "upload.txt"
    upload_path.write_bytes(b"hello")
    try:
        with patch("src.api.routes.documents.save_uploaded_file", return_value=(str(upload_path), "upload.txt")):
            with patch("src.api.routes.documents.enqueue_tracked_job", return_value=queued_job):
                with patch("src.api.routes.documents.audit_store.record_event", side_effect=RuntimeError("audit down")):
                    response = client.post(
                        f"/api/documents/{endpoint}?workspace_id=ws-a",
                        files={"file": ("upload.txt", b"hello", "text/plain")},
                    )

        assert response.status_code == 503
        assert upload_path.exists()
    finally:
        upload_path.unlink(missing_ok=True)
        teardown_test_env(tmp_dir, orig_db, patchers)


def test_upload_missing_mime_rejected_before_enqueue():
    _fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job") as mock_enqueue:
            response = client.post(
                "/api/documents/upload?workspace_id=ws-a",
                files={"file": ("upload.txt", b"hello", "")},
            )
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 400
    assert "MIME" in response.json()["detail"]
    mock_enqueue.assert_not_called()


def test_upload_stream_enqueues_job_and_streams_job_status_without_running_kb_import():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    queued_job = _job_payload("job-upload-stream-1")
    queued_job["job_type"] = "ingest_file"
    queued_job["workspace_id"] = "ws-a"
    running_job = {**queued_job, "status": "running", "progress": {"phase": "embedding", "percent": 60}}
    succeeded_job = {
        **queued_job,
        "status": "succeeded",
        "progress": {
            "phase": "done",
            "percent": 100,
            "result": {
                "chunk_count": 2,
                "total_docs": 5,
                "message": "已添加 2 个新段落",
                "suggested_questions": ["可以问什么？"],
                "existing_version": False,
            },
        },
    }
    uploaded_path = None
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job", return_value=queued_job) as mock_enqueue:
            with patch("src.api.routes.documents.job_store.get_job", side_effect=[running_job, succeeded_job]):
                with patch.object(fake_kb, "source_counts", return_value=[("upload.txt", 1)]):
                    with patch.object(fake_kb, "ingest_file") as mock_ingest_file:
                        response = client.post(
                            "/api/documents/upload-stream?workspace_id=ws-a&version_mode=append",
                            files={"file": ("upload.txt", b"hello", "text/plain")},
                        )
        call_kwargs = mock_enqueue.call_args.kwargs
        uploaded_path = call_kwargs["kwargs"]["file_path"]
    finally:
        if uploaded_path:
            Path(uploaded_path).unlink(missing_ok=True)
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events[0] == {"event": "progress", "data": {"phase": "embedding", "percent": 60}}
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["job_id"] == "job-upload-stream-1"
    assert events[-1]["data"]["chunk_count"] == 2
    assert events[-1]["data"]["suggested_questions"] == ["可以问什么？"]
    assert events[-1]["data"]["existing_version"] is True
    mock_ingest_file.assert_not_called()
    assert call_kwargs["job_type"] == "ingest_file"
    assert call_kwargs["target_path"] == "src.jobs.document_tasks:ingest_file_document"
    assert call_kwargs["workspace_id"] == "ws-a"
    assert call_kwargs["kwargs"]["source_name"] == "upload.txt"
    assert call_kwargs["kwargs"]["version_mode"] == "append"
    assert call_kwargs["inject_job_id"] is True


def test_ingest_url_returns_queued_job_without_running_kb_import():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job", return_value=_job_payload()) as mock_enqueue:
            with patch("src.api.routes.documents.audit_store.record_event") as mock_audit:
                with patch.object(fake_kb, "ingest_url") as mock_ingest_url:
                    response = client.post(
                        "/api/documents/ingest-url?workspace_id=ws-a&version_mode=append",
                        json={"url": "https://example.com/page?query=private#frag"},
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
            "url": "https://example.com/page?query=private#frag",
            "version_mode": "append",
            "workspace_id": "ws-a",
        },
        inject_job_id=True,
    )
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args.kwargs
    assert audit_kwargs["action"] == "document.url_import_queued"
    assert audit_kwargs["actor_user_id"] is None
    assert audit_kwargs["target_type"] == "job"
    assert audit_kwargs["target_id"] == "job-url-1"
    assert audit_kwargs["metadata"] == {
        "workspace_id": "ws-a",
        "job_type": "ingest_url",
        "version_mode": "append",
        "stream": False,
        "scheme": "https",
        "host": "example.com",
        "url": "https://example.com/page",
    }


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


def test_ingest_url_stream_enqueues_job_and_streams_job_status_without_running_kb_import():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    queued_job = _job_payload("job-url-stream-1")
    running_job = {**queued_job, "status": "running", "progress": {"phase": "loading", "percent": 25}}
    succeeded_job = {
        **queued_job,
        "status": "succeeded",
        "progress": {
            "phase": "done",
            "percent": 100,
            "result": {
                "chunk_count": 1,
                "total_docs": 3,
                "message": "已添加 1 个新段落",
                "suggested_questions": [],
                "existing_version": False,
            },
        },
    }
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job", return_value=queued_job) as mock_enqueue:
            with patch("src.api.routes.documents.audit_store.record_event") as mock_audit:
                with patch("src.api.routes.documents.job_store.get_job", side_effect=[running_job, succeeded_job]):
                    with patch.object(fake_kb, "ingest_url") as mock_ingest_url:
                        response = client.post(
                            "/api/documents/ingest-url-stream?workspace_id=ws-a&version_mode=append",
                            json={"url": "https://example.com/page?query=private#frag"},
                        )
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events[0] == {"event": "progress", "data": {"phase": "loading", "percent": 25}}
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["job_id"] == "job-url-stream-1"
    assert events[-1]["data"]["chunk_count"] == 1
    mock_ingest_url.assert_not_called()
    mock_enqueue.assert_called_once_with(
        job_type="ingest_url",
        target_path="src.jobs.document_tasks:ingest_url_document",
        created_by_user_id=None,
        workspace_id="ws-a",
        kwargs={
            "url": "https://example.com/page?query=private#frag",
            "version_mode": "append",
            "workspace_id": "ws-a",
        },
        inject_job_id=True,
    )
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args.kwargs
    assert audit_kwargs["action"] == "document.url_import_queued"
    assert audit_kwargs["target_id"] == "job-url-stream-1"
    assert audit_kwargs["metadata"] == {
        "workspace_id": "ws-a",
        "job_type": "ingest_url",
        "version_mode": "append",
        "stream": True,
        "scheme": "https",
        "host": "example.com",
        "url": "https://example.com/page",
    }


def test_delete_url_source_audit_redacts_query_and_fragment():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    try:
        with patch.object(fake_kb, "delete_source", return_value=1):
            with patch("src.api.routes.documents.audit_store.record_event") as mock_audit:
                response = client.delete(
                    "/api/documents/source/https%3A%2F%2Fexample.com%2Fpage%3Ftoken%3Dprivate%23frag"
                    "?workspace_id=ws-a"
                )
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args.kwargs
    assert audit_kwargs["action"] == "document.source_deleted"
    assert audit_kwargs["target_id"] == "https://example.com/page"
    assert audit_kwargs["metadata"] == {
        "workspace_id": "ws-a",
        "source_name": "https://example.com/page",
        "source_scheme": "https",
        "source_host": "example.com",
        "removed_chunks": 1,
    }


def test_clear_workspace_returns_queued_job_without_running_kb_clear():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    queued_job = _job_payload("job-clear-1")
    queued_job["job_type"] = "clear_workspace"
    queued_job["workspace_id"] = "ws-a"
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job", return_value=queued_job) as mock_enqueue:
            with patch("src.api.routes.documents.audit_store.record_event") as mock_audit:
                with patch.object(fake_kb, "clear_workspace") as mock_clear_workspace:
                    response = client.post("/api/documents/clear?workspace_id=ws-a")
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-clear-1"
    assert response.json()["job"]["status"] == "queued"
    mock_clear_workspace.assert_not_called()
    mock_enqueue.assert_called_once_with(
        job_type="clear_workspace",
        target_path="src.jobs.document_tasks:clear_workspace_documents",
        created_by_user_id=None,
        workspace_id="ws-a",
        kwargs={"workspace_id": "ws-a"},
        inject_job_id=True,
    )
    mock_audit.assert_called_once_with(
        action="document.clear_queued",
        actor_user_id=None,
        target_type="job",
        target_id="job-clear-1",
        metadata={"workspace_id": "ws-a", "job_type": "clear_workspace"},
    )


def test_rebuild_index_returns_queued_job_without_running_kb_rebuild():
    fake_kb, client, tmp_dir, orig_db, patchers = setup_test_env()
    queued_job = _job_payload("job-rebuild-1")
    queued_job["job_type"] = "rebuild_index"
    queued_job["workspace_id"] = "ws-a"
    try:
        with patch("src.api.routes.documents.enqueue_tracked_job", return_value=queued_job) as mock_enqueue:
            with patch("src.api.routes.documents.audit_store.record_event") as mock_audit:
                with patch.object(fake_kb, "rebuild_index", create=True) as mock_rebuild_index:
                    response = client.post("/api/documents/rebuild-index?workspace_id=ws-a")
    finally:
        teardown_test_env(tmp_dir, orig_db, patchers)

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-rebuild-1"
    assert response.json()["job"]["status"] == "queued"
    mock_rebuild_index.assert_not_called()
    mock_enqueue.assert_called_once_with(
        job_type="rebuild_index",
        target_path="src.jobs.document_tasks:rebuild_index_documents",
        created_by_user_id=None,
        workspace_id="ws-a",
        kwargs={"workspace_id": "ws-a"},
        inject_job_id=True,
    )
    mock_audit.assert_called_once_with(
        action="document.rebuild_queued",
        actor_user_id=None,
        target_type="job",
        target_id="job-rebuild-1",
        metadata={"workspace_id": "ws-a", "job_type": "rebuild_index"},
    )
