"""Regression coverage for workspace-scoped document and knowledge-base APIs."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src import conversations
from src.api.deps import get_knowledge_base
from src.api.main import app
from src.api.models import KBChunk
from src.rag.models import RetrievalResult


class WorkspaceScopedFakeKnowledgeBase:
    def __init__(self):
        self._loaded = False
        self._seq = 0
        self.all_docs: list[Document] = []
        self.doc_by_id: dict[str, Document] = {}
        self.hit_counter: dict[str, int] = {}

    def _next_chunk_id(self, workspace_id: str, source: str, chunk_index: int) -> str:
        self._seq += 1
        suffix = f"{self._seq:04d}"
        if workspace_id:
            return f"{workspace_id}::{source}:{chunk_index}:{suffix}"
        return f"{source}:{chunk_index}:{suffix}"

    def _add_doc(self, workspace_id: str, source: str, content: str, *, hits: int = 0, chunk_index: int | None = None) -> str:
        idx = chunk_index if chunk_index is not None else sum(
            1
            for doc in self.all_docs
            if doc.metadata.get("workspace_id", "") == workspace_id and doc.metadata.get("source") == source
        )
        chunk_id = self._next_chunk_id(workspace_id, source, idx)
        doc = Document(
            page_content=content,
            metadata={
                "source": source,
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "workspace_id": workspace_id,
            },
        )
        self.all_docs.append(doc)
        self.doc_by_id[chunk_id] = doc
        self.hit_counter[chunk_id] = hits
        return chunk_id

    def _ensure_loaded(self):
        if self._loaded:
            return
        self.default_shared_chunk_id = self._add_doc("", "shared.txt", "default shared knowledge", hits=2)
        self.default_only_chunk_id = self._add_doc("", "default-only.txt", "default only knowledge", hits=1)
        self.alpha_shared_chunk_id = self._add_doc("ws-alpha", "shared.txt", "alpha shared knowledge", hits=9)
        self.alpha_only_chunk_id = self._add_doc("ws-alpha", "alpha-only.txt", "alpha only knowledge", hits=6)
        self.beta_only_chunk_id = self._add_doc("ws-beta", "beta-only.txt", "beta only knowledge", hits=3)
        self._loaded = True

    def _workspace_docs(self, workspace_id: str | None = None) -> list[Document]:
        self._ensure_loaded()
        if workspace_id is None:
            return list(self.all_docs)
        return [doc for doc in self.all_docs if doc.metadata.get("workspace_id", "") == workspace_id]

    def source_counts(self, workspace_id: str | None = None):
        docs = self._workspace_docs(workspace_id)
        counts = Counter(doc.metadata.get("source", "未知来源") for doc in docs)
        return sorted(counts.items())

    @property
    def document_count(self):
        return len(self.all_docs)

    def document_count_for_workspace(self, workspace_id: str = ""):
        return len(self._workspace_docs(workspace_id))

    def stats(self, workspace_id: str = ""):
        docs = self._workspace_docs(workspace_id)
        return {
            "chunk_count": len(docs),
            "source_count": len(self.source_counts(workspace_id)),
            "total_chars": sum(len(doc.page_content) for doc in docs),
        }

    def list_chunks(self, *, workspace_id: str = "", source: str = "", search: str = "", skip: int = 0, limit: int = 50):
        docs = self._workspace_docs(workspace_id)
        if source:
            docs = [doc for doc in docs if doc.metadata.get("source") == source]
        if search:
            needle = search.lower()
            docs = [doc for doc in docs if needle in doc.page_content.lower()]
        total = len(docs)
        page = docs[skip: skip + limit]
        return total, [
            KBChunk(
                source=doc.metadata["source"],
                chunk_index=doc.metadata["chunk_index"],
                chunk_id=doc.metadata["chunk_id"],
                page=doc.metadata.get("page"),
                content=doc.page_content,
                original_content=doc.metadata.get("original_content"),
                section=doc.metadata.get("section"),
            )
            for doc in page
        ]

    def load_preset_documents(self):
        return 0

    def hybrid_search(self, *args, **kwargs):
        return []

    def debug_search_breakdown(self, query, k=5, vector_candidate_k=None, workspace_id=""):
        docs = [
            doc for doc in self._workspace_docs(workspace_id)
            if not query or query.lower() in doc.page_content.lower()
        ][:k]

        results = [
            RetrievalResult(
                chunk_id=doc.metadata["chunk_id"],
                document=doc,
                score=max(0.1, 1.0 - index * 0.1),
                vector_score=max(0.1, 1.0 - index * 0.1),
                bm25_score=max(0.1, 0.8 - index * 0.1),
            )
            for index, doc in enumerate(docs)
        ]
        return {
            "vector_results": results,
            "bm25_results": results,
            "fused_results": results,
        }

    def get_neighbor_chunks(self, chunk_id, window=1, workspace_id=None):
        return []

    def get_hotspots(self, top_n=50, workspace_id=None):
        docs = self._workspace_docs(workspace_id)
        ranked = sorted(
            docs,
            key=lambda doc: self.hit_counter.get(doc.metadata["chunk_id"], 0),
            reverse=True,
        )[:top_n]
        return [
            {
                "chunk_id": doc.metadata["chunk_id"],
                "source": doc.metadata["source"],
                "hits": self.hit_counter.get(doc.metadata["chunk_id"], 0),
                "content_preview": doc.page_content[:80],
            }
            for doc in ranked
        ]

    def get_chunk_by_id(self, chunk_id, workspace_id: str | None = None):
        for doc in self._workspace_docs(workspace_id):
            if doc.metadata["chunk_id"] == chunk_id:
                return {
                    "source": doc.metadata["source"],
                    "chunk_index": doc.metadata["chunk_index"],
                    "chunk_id": chunk_id,
                    "page": doc.metadata.get("page"),
                    "content": doc.page_content,
                    "original_content": doc.metadata.get("original_content"),
                    "section": doc.metadata.get("section"),
                }
        return None

    def ingest_file(self, file_path, source_name=None, version_mode="replace", progress_callback=None, workspace_id=""):
        if progress_callback:
            progress_callback("loading", 25)
        source = source_name or Path(file_path).name
        self._add_doc(workspace_id, source, f"uploaded into {workspace_id or 'default'} from {source}")
        return 1

    def ingest_url(self, url, version_mode="replace", progress_callback=None, workspace_id=""):
        if progress_callback:
            progress_callback("loading", 25)
        self._add_doc(workspace_id, url, f"url import for {workspace_id or 'default'}: {url}")
        return 1

    def delete_source(self, source_name, workspace_id=None):
        docs = self._workspace_docs(workspace_id)
        to_remove = [doc for doc in docs if doc.metadata.get("source") == source_name]
        if not to_remove:
            return 0
        remove_ids = {doc.metadata["chunk_id"] for doc in to_remove}
        self.all_docs = [doc for doc in self.all_docs if doc.metadata["chunk_id"] not in remove_ids]
        for chunk_id in remove_ids:
            self.doc_by_id.pop(chunk_id, None)
            self.hit_counter.pop(chunk_id, None)
        return len(to_remove)

    def clear_workspace(self, workspace_id=""):
        remove_ids = {
            doc.metadata["chunk_id"]
            for doc in self._workspace_docs(workspace_id)
        }
        self.all_docs = [doc for doc in self.all_docs if doc.metadata["chunk_id"] not in remove_ids]
        for chunk_id in remove_ids:
            self.doc_by_id.pop(chunk_id, None)
            self.hit_counter.pop(chunk_id, None)
        return len(remove_ids)

    def clear(self):
        self.all_docs = []
        self.doc_by_id = {}
        self.hit_counter = {}
        self._loaded = False
        self._seq = 0


class WorkspaceScopedKnowledgeBaseApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher_chroma = patch("src.rag.knowledge_base.Chroma")
        cls.patcher_embeddings = patch("src.rag.knowledge_base.OpenAIEmbeddings")
        cls.patcher_api_key = patch("src.rag.knowledge_base.require_siliconflow_api_key", return_value="sk-test")

        cls.patcher_chroma.start()
        cls.patcher_embeddings.start()
        cls.patcher_api_key.start()

        cls.fake_kb = WorkspaceScopedFakeKnowledgeBase()
        app.dependency_overrides[get_knowledge_base] = lambda: cls.fake_kb

        cls._temp_dir = tempfile.TemporaryDirectory()
        cls._original_db_path = conversations._DB_PATH
        conversations._DB_PATH = Path(cls._temp_dir.name) / "conversations.db"
        conversations.init_db()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        conversations._DB_PATH = cls._original_db_path
        cls._temp_dir.cleanup()
        app.dependency_overrides.clear()
        cls.patcher_chroma.stop()
        cls.patcher_embeddings.stop()
        cls.patcher_api_key.stop()

    def setUp(self):
        self.fake_kb.clear()
        self.fake_kb._ensure_loaded()

    def test_openapi_declares_workspace_scope_for_kb_and_document_routes(self):
        spec_path = Path(__file__).resolve().parents[1] / "openapi.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))

        expected = [
            ("/api/documents/sources", "get"),
            ("/api/documents/check-source", "get"),
            ("/api/documents/upload-stream", "post"),
            ("/api/documents/ingest-url-stream", "post"),
            ("/api/documents/upload", "post"),
            ("/api/documents/ingest-url", "post"),
            ("/api/documents/source/{source_name}", "delete"),
            ("/api/documents/clear", "post"),
            ("/api/knowledge-base/stats", "get"),
            ("/api/knowledge-base/chunks", "get"),
            ("/api/knowledge-base/chunks/{chunk_id}", "get"),
            ("/api/knowledge-base/sources", "get"),
            ("/api/knowledge-base/hotspots", "get"),
            ("/api/knowledge-base/debug-search", "post"),
        ]

        for path, method in expected:
            params = spec["paths"][path][method].get("parameters", [])
            param_names = {param["name"] for param in params}
            self.assertIn("workspace_id", param_names, f"{method.upper()} {path} should declare workspace_id")

    def test_sources_stats_chunks_and_hotspots_are_workspace_scoped(self):
        sources_resp = self.client.get("/api/documents/sources?workspace_id=ws-alpha")
        self.assertEqual(sources_resp.status_code, 200)
        self.assertEqual(
            sources_resp.json(),
            [
                {"source": "alpha-only.txt", "count": 1},
                {"source": "shared.txt", "count": 1},
            ],
        )

        kb_sources_resp = self.client.get("/api/knowledge-base/sources?workspace_id=ws-alpha")
        self.assertEqual(kb_sources_resp.status_code, 200)
        self.assertEqual(kb_sources_resp.json(), ["alpha-only.txt", "shared.txt"])

        stats_resp = self.client.get("/api/knowledge-base/stats?workspace_id=ws-alpha")
        self.assertEqual(stats_resp.status_code, 200)
        self.assertEqual(stats_resp.json()["chunk_count"], 2)
        self.assertEqual(stats_resp.json()["source_count"], 2)

        chunks_resp = self.client.get("/api/knowledge-base/chunks?workspace_id=ws-alpha&skip=0&limit=20")
        self.assertEqual(chunks_resp.status_code, 200)
        self.assertEqual(chunks_resp.json()["total"], 2)
        self.assertTrue(all(item["chunk_id"].startswith("ws-alpha::") for item in chunks_resp.json()["items"]))

        hotspots_resp = self.client.get("/api/knowledge-base/hotspots?workspace_id=ws-alpha")
        self.assertEqual(hotspots_resp.status_code, 200)
        hotspot_ids = [item["chunk_id"] for item in hotspots_resp.json()]
        self.assertEqual(hotspot_ids, [self.fake_kb.alpha_shared_chunk_id, self.fake_kb.alpha_only_chunk_id])

    def test_chunk_lookup_and_debug_search_do_not_cross_workspaces(self):
        ok_resp = self.client.get(f"/api/knowledge-base/chunks/{self.fake_kb.alpha_shared_chunk_id}?workspace_id=ws-alpha")
        self.assertEqual(ok_resp.status_code, 200)
        self.assertEqual(ok_resp.json()["chunk_id"], self.fake_kb.alpha_shared_chunk_id)

        hidden_resp = self.client.get(f"/api/knowledge-base/chunks/{self.fake_kb.default_shared_chunk_id}?workspace_id=ws-alpha")
        self.assertEqual(hidden_resp.status_code, 404)

        search_resp = self.client.post(
            "/api/knowledge-base/debug-search?workspace_id=ws-alpha",
            json={"query": "knowledge", "k": 5, "search_strategy": "balanced"},
        )
        self.assertEqual(search_resp.status_code, 200)
        fused_ids = [item["chunk_id"] for item in search_resp.json()["fused_results"]]
        self.assertEqual(set(fused_ids), {self.fake_kb.alpha_shared_chunk_id, self.fake_kb.alpha_only_chunk_id})
        self.assertNotIn(self.fake_kb.default_shared_chunk_id, fused_ids)

    def test_check_source_upload_and_url_ingest_only_touch_target_workspace(self):
        check_resp = self.client.get("/api/documents/check-source?source_name=shared.txt&workspace_id=ws-alpha")
        self.assertEqual(check_resp.status_code, 200)
        self.assertEqual(check_resp.json(), {"exists": True})

        missing_resp = self.client.get("/api/documents/check-source?source_name=shared.txt&workspace_id=ws-beta")
        self.assertEqual(missing_resp.status_code, 200)
        self.assertEqual(missing_resp.json(), {"exists": False})

        upload_resp = self.client.post(
            "/api/documents/upload?workspace_id=ws-beta",
            files={"file": ("workspace-beta.txt", b"beta content", "text/plain")},
        )
        self.assertEqual(upload_resp.status_code, 200)
        self.assertEqual(upload_resp.json()["chunk_count"], 1)

        beta_sources_after_upload = self.client.get("/api/documents/sources?workspace_id=ws-beta").json()
        self.assertEqual(
            beta_sources_after_upload,
            [
                {"source": "beta-only.txt", "count": 1},
                {"source": "workspace-beta.txt", "count": 1},
            ],
        )

        default_sources = self.client.get("/api/documents/sources?workspace_id=").json()
        self.assertEqual(
            default_sources,
            [
                {"source": "default-only.txt", "count": 1},
                {"source": "shared.txt", "count": 1},
            ],
        )

        ingest_resp = self.client.post(
            "/api/documents/ingest-url?workspace_id=ws-beta",
            json={"url": "https://example.com/beta"},
        )
        self.assertEqual(ingest_resp.status_code, 200)
        self.assertEqual(ingest_resp.json()["chunk_count"], 1)

        beta_stats = self.client.get("/api/knowledge-base/stats?workspace_id=ws-beta").json()
        self.assertEqual(beta_stats["chunk_count"], 3)

    def test_delete_source_only_removes_requested_workspace(self):
        resp = self.client.delete("/api/documents/source/shared.txt?workspace_id=ws-alpha")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["chunk_count"], 1)

        alpha_sources = self.client.get("/api/documents/sources?workspace_id=ws-alpha").json()
        self.assertEqual(alpha_sources, [{"source": "alpha-only.txt", "count": 1}])

        default_sources = self.client.get("/api/documents/sources?workspace_id=").json()
        self.assertEqual(
            default_sources,
            [
                {"source": "default-only.txt", "count": 1},
                {"source": "shared.txt", "count": 1},
            ],
        )

    def test_clear_only_removes_requested_workspace(self):
        resp = self.client.post("/api/documents/clear?workspace_id=ws-alpha")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["removed"], 2)

        alpha_stats = self.client.get("/api/knowledge-base/stats?workspace_id=ws-alpha").json()
        self.assertEqual(alpha_stats["chunk_count"], 0)

        default_stats = self.client.get("/api/knowledge-base/stats?workspace_id=").json()
        self.assertEqual(default_stats["chunk_count"], 2)

        beta_stats = self.client.get("/api/knowledge-base/stats?workspace_id=ws-beta").json()
        self.assertEqual(beta_stats["chunk_count"], 1)
