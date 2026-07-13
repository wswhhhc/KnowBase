from __future__ import annotations

from src.api.document_job_stream import done_payload, progress_payload
from src.services.document_audit import redacted_url_for_audit, source_audit_identity


def test_redacted_url_for_audit_removes_credentials_query_and_fragment():
    result = redacted_url_for_audit("https://user:secret@example.com:8443/path?token=private#section")

    assert result == {
        "scheme": "https",
        "host": "example.com",
        "url": "https://example.com:8443/path",
    }


def test_source_audit_identity_preserves_plain_source_names():
    target_id, metadata = source_audit_identity("meeting_notes.md")

    assert target_id == "meeting_notes.md"
    assert metadata == {"source_name": "meeting_notes.md"}


def test_source_audit_identity_redacts_web_source_names():
    target_id, metadata = source_audit_identity("https://example.com/page?token=private#section")

    assert target_id == "https://example.com/page"
    assert metadata == {
        "source_name": "https://example.com/page",
        "source_scheme": "https",
        "source_host": "example.com",
    }


def test_progress_payload_excludes_terminal_result():
    assert progress_payload({"phase": "done", "percent": 100, "result": {"chunk_count": 2}}) == {
        "phase": "done",
        "percent": 100,
    }


def test_done_payload_preserves_existing_version_from_fallback():
    job = {
        "id": "job-1",
        "progress": {"result": {"chunk_count": 2, "existing_version": False}},
    }

    result = done_payload(job, {"existing_version": True, "message": "导入任务已完成"})

    assert result == {
        "chunk_count": 2,
        "existing_version": True,
        "message": "导入任务已完成",
        "job_id": "job-1",
    }
