from __future__ import annotations

from src.api.auth_tokens import hash_password
from src.jobs.document_tasks import ingest_url_document
from src.persistence import auth_store, job_store
from tests.test_auth_routes import _configure_auth_database


class FakeKnowledgeBase:
    def __init__(self):
        self.ingest_calls = []
        self.progress_callback = None

    def ingest_url(self, url, version_mode="replace", progress_callback=None, workspace_id=""):
        self.ingest_calls.append(
            {"url": url, "version_mode": version_mode, "workspace_id": workspace_id}
        )
        self.progress_callback = progress_callback
        if progress_callback:
            progress_callback("loading", 25)
            progress_callback("embedding", 75)
        return 2

    def list_chunks(self, *, workspace_id="", source="", limit=1000):
        return 1, []

    def document_count_for_workspace(self, workspace_id=""):
        return 5


def test_ingest_url_document_runs_kb_import_and_updates_job_progress(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="ingest_url", created_by_user_id=user["id"])
    kb = FakeKnowledgeBase()

    result = ingest_url_document(
        url="https://example.com/page",
        version_mode="append",
        workspace_id="ws-a",
        job_id=job["id"],
        kb=kb,
    )
    stored = job_store.get_job(job["id"])

    assert kb.ingest_calls == [
        {"url": "https://example.com/page", "version_mode": "append", "workspace_id": "ws-a"}
    ]
    assert result["chunk_count"] == 2
    assert result["total_docs"] == 5
    assert result["message"] == "已添加 2 个新段落"
    assert stored is not None
    assert stored["progress"] == {
        "phase": "finalizing",
        "percent": 95,
        "message": "已添加 2 个新段落",
    }
