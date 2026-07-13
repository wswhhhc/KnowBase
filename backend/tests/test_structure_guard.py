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
        "generate_suggested_questions('content')"
    )

    assert len(violations) == 4


def test_documents_route_matches_the_extracted_boundary():
    assert guard._check_documents_route_boundaries() == []
