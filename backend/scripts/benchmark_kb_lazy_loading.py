"""Synthetic benchmark for KB lazy-loading behavior.

Usage:
    uv run python backend/scripts/benchmark_kb_lazy_loading.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.rag.knowledge_base import KnowledgeBase


def _make_doc(index: int, workspace_id: str = "") -> Document:
    source = f"doc-{index // 10}.md"
    chunk_id = f"{workspace_id + '::' if workspace_id else ''}{source}:{index}:hash{index:05d}"
    text = (f"alpha beta gamma chunk {index} for workspace {workspace_id or 'default'}. " * 12).strip()
    return Document(
        page_content=text,
        metadata={
            "source": source,
            "chunk_id": chunk_id,
            "chunk_index": index,
            "workspace_id": workspace_id,
            "content_hash": f"hash{index:05d}",
            "source_type": "local_file",
        },
    )


class _FakeChroma:
    def __init__(self, docs: list[Document]):
        self.docs = list(docs)
        self._collection = MagicMock()

    def get(self, include: list[str] | None = None):
        include = include or []
        ids = [doc.metadata["chunk_id"] for doc in self.docs]
        result = {"ids": ids}
        if "documents" in include:
            result["documents"] = [doc.page_content for doc in self.docs]
        if "metadatas" in include:
            result["metadatas"] = [dict(doc.metadata) for doc in self.docs]
        return result

    def similarity_search_with_score(self, _query: str, k: int, filter: dict | None = None):
        workspace_id = None if filter is None else filter.get("workspace_id")
        scoped = [
            doc for doc in self.docs
            if workspace_id is None or doc.metadata.get("workspace_id", "") == workspace_id
        ]
        return [(doc, 1.0 / (index + 1)) for index, doc in enumerate(scoped[:k])]

    def add_documents(self, docs: list[Document], ids: list[str] | None = None) -> None:
        for index, doc in enumerate(docs):
            copied = Document(page_content=doc.page_content, metadata=dict(doc.metadata))
            if ids and index < len(ids):
                copied.metadata["chunk_id"] = ids[index]
            self.docs.append(copied)

    def delete(self, ids: list[str] | None = None) -> None:
        removed = set(ids or [])
        self.docs = [doc for doc in self.docs if doc.metadata.get("chunk_id") not in removed]

    def delete_collection(self) -> None:
        self.docs = []


def _import_payload(repeat: int) -> list[Document]:
    return [Document(page_content=("新的导入内容 alpha beta gamma。\n" * repeat), metadata={"source": "import.md"})]


def _run_case(existing_chunks: int, *, repeats: int, import_repeat: int) -> dict[str, object]:
    init_samples: list[float] = []
    first_search_samples: list[float] = []
    import_samples: list[float] = []
    prepared_chunks = 0
    imported_chunks = 0
    search_forced_doc_load = False
    search_built_bm25 = False
    import_forced_doc_load = False

    for _ in range(repeats):
        docs = [_make_doc(index) for index in range(existing_chunks)]
        fake_store = _FakeChroma(docs)
        with patch("src.rag.knowledge_base.require_siliconflow_api_key", return_value="sk-test"), \
             patch("src.rag.knowledge_base.OpenAIEmbeddings"), \
             patch("src.rag.knowledge_base.Chroma", return_value=fake_store), \
             patch.object(KnowledgeBase, "_read_index_metadata", return_value={}), \
             patch.object(KnowledgeBase, "_write_index_metadata", return_value=None):
            start = time.perf_counter()
            kb = KnowledgeBase()
            init_samples.append((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            results = kb.hybrid_search("alpha beta", k=8, score_threshold=None, workspace_id="")
            first_search_samples.append((time.perf_counter() - start) * 1000)
            if not results:
                raise RuntimeError("benchmark search returned no results")
            search_forced_doc_load = search_forced_doc_load or kb.ingestion._loaded
            search_built_bm25 = search_built_bm25 or kb.state.bm25_loaded

            payload = _import_payload(import_repeat)
            prepared_chunks = len(kb.ingestion._prepare_splits(payload))
            start = time.perf_counter()
            imported_chunks = kb.ingestion._process_documents(payload)
            import_samples.append((time.perf_counter() - start) * 1000)
            import_forced_doc_load = import_forced_doc_load or kb.ingestion._loaded

    return {
        "existing_chunks": existing_chunks,
        "prepared_chunks": prepared_chunks,
        "imported_chunks": imported_chunks,
        "init_ms": round(statistics.mean(init_samples), 2),
        "first_search_ms": round(statistics.mean(first_search_samples), 2),
        "import_ms": round(statistics.mean(import_samples), 2),
        "search_forced_doc_load": search_forced_doc_load,
        "search_built_bm25": search_built_bm25,
        "import_forced_doc_load": import_forced_doc_load,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[500, 2000, 5000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--import-repeat", type=int, default=1200)
    args = parser.parse_args()

    cases = [
        _run_case(size, repeats=args.repeats, import_repeat=args.import_repeat)
        for size in args.sizes
    ]
    print(json.dumps(cases, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
