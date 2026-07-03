"""Persistence for retrieval hotspot counters."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_core.documents import Document


logger = logging.getLogger(__name__)


class HotspotTracker:
    """Tracks document retrieval hit counts, persisted to JSON."""

    def __init__(self, hotspot_path: Path):
        self.hit_counter: dict[str, int] = {}
        self._hotspot_dirty = False
        self._hotspot_path = hotspot_path
        self._load_hotspots()

    def _load_hotspots(self) -> None:
        try:
            if self._hotspot_path.exists():
                with open(self._hotspot_path, encoding="utf-8") as file:
                    self.hit_counter = json.load(file)
        except Exception as exc:
            logger.warning("热点计数加载失败: %s", exc)
            self.hit_counter = {}

    def _save_hotspots(self) -> None:
        if not self._hotspot_dirty:
            return
        try:
            self._hotspot_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._hotspot_path, "w", encoding="utf-8") as file:
                json.dump(self.hit_counter, file, ensure_ascii=False)
            self._hotspot_dirty = False
        except Exception as exc:
            logger.warning("热点计数持久化失败: %s", exc)

    def record_hit(self, chunk_id: str) -> None:
        self.hit_counter[chunk_id] = self.hit_counter.get(chunk_id, 0) + 1
        self._hotspot_dirty = True

    def get_hotspots(self, top_n: int, doc_by_id: dict[str, Document]) -> list[dict]:
        sorted_chunks = sorted(
            self.hit_counter.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        result = []
        for chunk_id, hits in sorted_chunks[:top_n]:
            doc = doc_by_id.get(chunk_id)
            result.append({
                "chunk_id": chunk_id,
                "source": doc.metadata.get("source", "") if doc else "",
                "hits": hits,
                "content_preview": doc.page_content[:80] if doc else "",
            })
        return result

    def clear(self) -> None:
        self.hit_counter = {}
        self._hotspot_dirty = True
        self._save_hotspots()
