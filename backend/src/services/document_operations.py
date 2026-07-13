"""Synchronous document operations shared by HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.chat_utils import generate_suggested_questions
from src.rag.models import normalize_source


class DocumentOperationsKnowledgeBase(Protocol):
    def import_demo_documents(self, workspace_id: str = "") -> tuple[int, list[str]]: ...

    def list_chunks(
        self,
        *,
        workspace_id: str = "",
        source: str = "",
        limit: int = 50,
    ) -> tuple[int, list]: ...

    def delete_source(self, source_name: str, workspace_id: str = "") -> int: ...

    def document_count_for_workspace(self, workspace_id: str = "") -> int: ...


@dataclass(frozen=True)
class DemoImportResult:
    chunk_count: int
    total_docs: int
    message: str
    imported_sources: list[str]
    suggested_questions: list[str]


@dataclass(frozen=True)
class DeletedSourceResult:
    chunk_count: int
    total_docs: int
    message: str


def collect_suggested_questions(
    kb: DocumentOperationsKnowledgeBase,
    source_names: list[str],
    *,
    workspace_id: str = "",
) -> list[str]:
    texts: list[str] = []
    seen_sources: set[str] = set()
    for source_name in source_names:
        normalized = normalize_source(source_name)
        if normalized in seen_sources:
            continue
        seen_sources.add(normalized)
        _total, source_chunks = kb.list_chunks(
            workspace_id=workspace_id,
            source=source_name,
            limit=1000,
        )
        if source_chunks:
            texts.append(" ".join(chunk.content for chunk in source_chunks))
    docs_text = " ".join(texts).strip()
    return generate_suggested_questions(docs_text) if docs_text else []


def import_demo_documents(
    kb: DocumentOperationsKnowledgeBase,
    *,
    workspace_id: str = "",
) -> DemoImportResult:
    chunk_count, imported_sources = kb.import_demo_documents(workspace_id=workspace_id)
    suggested = collect_suggested_questions(kb, imported_sources, workspace_id=workspace_id)
    message = f"已导入 {len(imported_sources)} 份示例资料" if chunk_count > 0 else "示例资料已在当前工作区就绪"
    return DemoImportResult(
        chunk_count=chunk_count,
        total_docs=kb.document_count_for_workspace(workspace_id),
        message=message,
        imported_sources=imported_sources,
        suggested_questions=suggested,
    )


def delete_source(
    kb: DocumentOperationsKnowledgeBase,
    source_name: str,
    *,
    workspace_id: str = "",
) -> DeletedSourceResult | None:
    removed = kb.delete_source(source_name, workspace_id=workspace_id)
    if removed == 0:
        return None
    return DeletedSourceResult(
        chunk_count=removed,
        total_docs=kb.document_count_for_workspace(workspace_id),
        message=f"已删除 {source_name}（{removed} 个段落）",
    )
