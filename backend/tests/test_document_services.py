from __future__ import annotations

import asyncio
import json
from unittest.mock import Mock

from src.api.document_job_stream import done_event_source, done_payload, job_event_source, progress_payload
from src.services.document_audit import redacted_url_for_audit, source_audit_identity
from src.services.document_import_service import source_exists, submit_file_import, submit_url_import
from src.services.document_job_service import enqueue_clear_workspace, enqueue_rebuild_index
from src.services.document_operations import delete_source, import_demo_documents


def _collect_sse_events(response) -> list[dict]:
    async def collect() -> list[dict]:
        events = []
        async for item in response.body_iterator:
            events.append({"event": item["event"], "data": json.loads(item["data"])})
        return events

    return asyncio.run(collect())


def test_done_event_source_emits_exactly_one_done_event():
    response = done_event_source({"existing_version": True, "message": "请选择版本策略"})

    assert _collect_sse_events(response) == [
        {
            "event": "done",
            "data": {"existing_version": True, "message": "请选择版本策略"},
        }
    ]


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


def test_job_event_source_uses_fallback_when_succeeded_job_has_no_result():
    response = job_event_source(
        "job-1",
        fallback_done={"chunk_count": 0, "message": "导入任务已完成"},
        get_job=lambda _job_id: {
            "id": "job-1",
            "status": "succeeded",
            "progress": {"phase": "done", "percent": 100},
        },
        poll_seconds=0,
    )

    assert _collect_sse_events(response) == [
        {"event": "progress", "data": {"phase": "done", "percent": 100}},
        {
            "event": "done",
            "data": {"chunk_count": 0, "message": "导入任务已完成", "job_id": "job-1"},
        },
    ]


def test_job_event_source_deduplicates_progress_before_failed_error():
    jobs = iter(
        [
            {
                "id": "job-1",
                "status": "running",
                "progress": {"phase": "embedding", "percent": 60},
            },
            {
                "id": "job-1",
                "status": "failed",
                "progress": {"phase": "embedding", "percent": 60},
                "error": "embedding failed",
            },
        ]
    )
    response = job_event_source(
        "job-1",
        fallback_done={},
        get_job=lambda _job_id: next(jobs),
        poll_seconds=0,
    )

    assert _collect_sse_events(response) == [
        {"event": "progress", "data": {"phase": "embedding", "percent": 60}},
        {"event": "error", "data": {"job_id": "job-1", "message": "embedding failed"}},
    ]


def test_job_event_source_emits_canceled_error_after_progress():
    response = job_event_source(
        "job-1",
        fallback_done={},
        get_job=lambda _job_id: {
            "id": "job-1",
            "status": "canceled",
            "progress": {"phase": "queued", "percent": 0},
        },
        poll_seconds=0,
    )

    assert _collect_sse_events(response) == [
        {"event": "progress", "data": {"phase": "queued", "percent": 0}},
        {"event": "error", "data": {"job_id": "job-1", "message": "导入任务已取消"}},
    ]


def test_job_event_source_emits_error_when_job_is_missing():
    response = job_event_source(
        "missing-job",
        fallback_done={},
        get_job=lambda _job_id: None,
        poll_seconds=0,
    )

    assert _collect_sse_events(response) == [
        {"event": "error", "data": {"job_id": "missing-job", "message": "任务不存在"}}
    ]


class _SourceKnowledgeBase:
    def source_counts(self, *, workspace_id: str):
        assert workspace_id == "ws-a"
        return [("meeting_notes.md (v1)", 2)]


def test_source_exists_matches_ui_version_suffixes():
    assert source_exists(_SourceKnowledgeBase(), "meeting_notes.md", workspace_id="ws-a") is True


def test_submit_file_import_returns_probe_without_enqueuing_existing_source():
    enqueue_job = Mock()

    result = submit_file_import(
        _SourceKnowledgeBase(),
        file_path="runtime/local/uploads/upload.txt",
        source_name="meeting_notes.md",
        version_mode=None,
        workspace_id="ws-a",
        actor_user_id="user-1",
        enqueue_job=enqueue_job,
    )

    assert result.existing_version is True
    assert result.job is None
    assert result.version_mode is None
    enqueue_job.assert_not_called()


def test_submit_url_import_enqueues_default_replace_mode():
    enqueue_job = Mock(return_value={"id": "job-url-1"})

    result = submit_url_import(
        _SourceKnowledgeBase(),
        url="https://example.com/page",
        version_mode="append",
        workspace_id="ws-a",
        actor_user_id="user-1",
        enqueue_job=enqueue_job,
    )

    assert result.existing_version is False
    assert result.version_mode == "append"
    assert result.job == {"id": "job-url-1"}
    enqueue_job.assert_called_once_with(
        job_type="ingest_url",
        target_path="src.jobs.document_tasks:ingest_url_document",
        created_by_user_id="user-1",
        workspace_id="ws-a",
        kwargs={
            "url": "https://example.com/page",
            "version_mode": "append",
            "workspace_id": "ws-a",
        },
        inject_job_id=True,
    )


class _OperationsKnowledgeBase:
    def import_demo_documents(self, *, workspace_id: str):
        assert workspace_id == "ws-a"
        return 2, ["demo.md"]

    def list_chunks(self, *, workspace_id: str, source: str, limit: int):
        assert (workspace_id, source, limit) == ("ws-a", "demo.md", 1000)
        return 1, [type("Chunk", (), {"content": "demo content"})()]

    def document_count_for_workspace(self, workspace_id: str):
        assert workspace_id == "ws-a"
        return 3

    def delete_source(self, source_name: str, *, workspace_id: str):
        assert (source_name, workspace_id) == ("demo.md", "ws-a")
        return 2


def test_import_demo_documents_builds_response_data_and_suggestions(monkeypatch):
    monkeypatch.setattr(
        "src.services.document_operations.generate_suggested_questions",
        lambda text: [f"ask about {text}"],
    )

    result = import_demo_documents(_OperationsKnowledgeBase(), workspace_id="ws-a")

    assert result.chunk_count == 2
    assert result.total_docs == 3
    assert result.message == "已导入 1 份示例资料"
    assert result.imported_sources == ["demo.md"]
    assert result.suggested_questions == ["ask about demo content"]


def test_delete_source_returns_none_when_no_chunks_are_removed():
    class EmptyOperationsKnowledgeBase:
        def delete_source(self, source_name: str, *, workspace_id: str):
            return 0

    assert delete_source(EmptyOperationsKnowledgeBase(), "missing.md", workspace_id="ws-a") is None


def test_enqueue_clear_workspace_uses_fixed_job_contract_and_records_audit():
    enqueue_job = Mock(return_value={"id": "job-clear-1"})
    record_event = Mock()

    result = enqueue_clear_workspace(
        workspace_id="ws-a",
        actor_user_id="user-1",
        enqueue_job=enqueue_job,
        record_event=record_event,
    )

    assert result == {"id": "job-clear-1"}
    enqueue_job.assert_called_once_with(
        job_type="clear_workspace",
        target_path="src.jobs.document_tasks:clear_workspace_documents",
        created_by_user_id="user-1",
        workspace_id="ws-a",
        kwargs={"workspace_id": "ws-a"},
        inject_job_id=True,
    )
    record_event.assert_called_once_with(
        action="document.clear_queued",
        actor_user_id="user-1",
        target_type="job",
        target_id="job-clear-1",
        metadata={"workspace_id": "ws-a", "job_type": "clear_workspace"},
    )


def test_enqueue_rebuild_index_uses_fixed_job_contract_and_records_audit():
    enqueue_job = Mock(return_value={"id": "job-rebuild-1"})
    record_event = Mock()

    result = enqueue_rebuild_index(
        workspace_id="ws-a",
        actor_user_id="user-1",
        enqueue_job=enqueue_job,
        record_event=record_event,
    )

    assert result == {"id": "job-rebuild-1"}
    enqueue_job.assert_called_once_with(
        job_type="rebuild_index",
        target_path="src.jobs.document_tasks:rebuild_index_documents",
        created_by_user_id="user-1",
        workspace_id="ws-a",
        kwargs={"workspace_id": "ws-a"},
        inject_job_id=True,
    )
    record_event.assert_called_once_with(
        action="document.rebuild_queued",
        actor_user_id="user-1",
        target_type="job",
        target_id="job-rebuild-1",
        metadata={"workspace_id": "ws-a", "job_type": "rebuild_index"},
    )
