from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_structure", ROOT / "scripts" / "check-structure.py")
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def test_documents_route_boundary_helper_detects_relocated_business_logic():
    violations = guard._document_route_boundary_violations(
        "asyncio.sleep(0.1)\naudit_store.record_event(action='x')\n"
        "target_path='src.jobs.document_tasks:clear_workspace_documents'\n"
        "generate_suggested_questions('content')\n"
        "EventSourceResponse(stream())\n"
        "job_store.get_job('job-1')\n"
        "enqueue_tracked_job(job_type='clear_workspace')"
    )

    assert len(violations) == 7


def test_documents_route_matches_the_extracted_boundary():
    assert guard._check_documents_route_boundaries() == []


def test_service_boundary_helper_detects_fastapi_and_api_model_imports():
    violations = guard._service_boundary_violations(
        "from fastapi import HTTPException\n"
        "from src.api.models import IngestResponse\n"
        "from sse_starlette.sse import EventSourceResponse"
    )

    assert len(violations) == 3


def test_service_boundary_helper_ignores_similarly_named_modules():
    assert guard._service_boundary_violations(
        "import fastapi_utils\nimport src.api.models_extra"
    ) == []


def test_services_match_the_application_boundary():
    assert guard._check_service_boundaries() == []


def test_frontend_boundary_helpers_detect_known_api_and_preference_regressions():
    assert guard._document_panel_boundary_violations("import * as api from '@/shared/api'")
    assert guard._chat_page_preference_violations("localStorage.setItem('kb_search_strategy', 'deep')")


def test_document_panel_boundary_detects_runtime_subpath_and_default_imports():
    assert guard._document_panel_boundary_violations(
        "import { uploadDocument } from '@/shared/api/documents'"
    )
    assert guard._document_panel_boundary_violations(
        "import documentsApi from '@/shared/api/documents'"
    )


def test_document_panel_boundary_allows_type_only_api_imports():
    assert guard._document_panel_boundary_violations(
        "import type { DocSource } from '@/shared/api'"
    ) == []
    assert guard._document_panel_boundary_violations(
        "import { type DocSource, type Job } from '@/shared/api'"
    ) == []


def test_document_panel_boundary_detects_mixed_type_and_runtime_imports():
    assert guard._document_panel_boundary_violations(
        "import { type DocSource, uploadDocument } from '@/shared/api'"
    )


def test_chat_page_preference_boundary_detects_keys_stored_in_variables():
    assert guard._chat_page_preference_violations(
        "const key = 'kb_search_strategy'\nlocalStorage.setItem(key, 'deep')"
    )


def test_frontend_boundaries_match_the_extracted_modules():
    assert guard._check_document_panel_boundaries() == []
    assert guard._check_chat_page_preference_boundaries() == []
