"""Quickstart demo for KnowBase.

Loads a small bundled demo knowledge base into an isolated runtime directory and
optionally asks a few canned questions so new users can validate the full RAG
loop with the smallest possible setup.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEMO_SOURCE_DIR = REPO_ROOT / "examples" / "demo-documents"
DEMO_RUNTIME_DIR = REPO_ROOT / "runtime" / "quickstart"
DEMO_CHROMA_DIR = DEMO_RUNTIME_DIR / "chroma_db"
DEMO_CHECKPOINT_DB = DEMO_RUNTIME_DIR / "checkpoints.db"

DEFAULT_QUESTIONS = [
    "甲方解除合同前需要提前多少天书面通知？",
    "支付网关灰度上线的日期是什么时候？",
    "批量导入接口单次最多支持多少条记录？",
]


def _demo_documents() -> list[Path]:
    return sorted(path for path in DEMO_SOURCE_DIR.glob("*") if path.is_file())


def _runtime_summary() -> str:
    doc_lines = "\n".join(f"  - {path.name}" for path in _demo_documents())
    question_lines = "\n".join(f"  - {question}" for question in DEFAULT_QUESTIONS)
    return (
        f"Demo source dir: {DEMO_SOURCE_DIR}\n"
        f"Demo runtime dir: {DEMO_RUNTIME_DIR}\n"
        f"Demo Chroma dir: {DEMO_CHROMA_DIR}\n"
        f"Demo checkpoint DB: {DEMO_CHECKPOINT_DB}\n"
        f"Bundled documents:\n{doc_lines}\n"
        f"Suggested questions:\n{question_lines}"
    )


def _configure_demo_env(reset: bool) -> None:
    if reset and DEMO_RUNTIME_DIR.exists():
        shutil.rmtree(DEMO_RUNTIME_DIR)

    DEMO_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["DATA_DIR"] = str(DEMO_RUNTIME_DIR)
    os.environ["CHROMA_PERSIST_DIR"] = str(DEMO_CHROMA_DIR)
    os.environ["CHECKPOINT_DB_PATH"] = str(DEMO_CHECKPOINT_DB)


def _load_demo_documents() -> tuple[object, int]:
    sys.path.insert(0, str(BACKEND_ROOT))

    from src.rag.knowledge_base import KnowledgeBase

    kb = KnowledgeBase()
    total = 0
    for path in _demo_documents():
        total += kb.ingest_file(str(path), source_name=path.name, version_mode="replace")
    return kb, total


def _run_questions(kb: object, questions: list[str]) -> None:
    from src.graph import run_query

    for index, question in enumerate(questions, 1):
        result = run_query(
            question=question,
            thread_id=f"quickstart-{uuid4()}",
            knowledge_base=kb,
            web_search_enabled=False,
        )
        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n[{index}] 问题: {question}")
        print(f"答案: {answer}")
        if sources:
            print("引用来源:")
            for source in sources[:3]:
                print(f"  - {source.get('source', '未知来源')} ({source.get('chunk_id', '')})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the KnowBase 5-minute demo.")
    parser.add_argument("--dry-run", action="store_true", help="Print demo paths and bundled files without loading models.")
    parser.add_argument("--reset", action="store_true", help="Delete the isolated quickstart runtime directory before loading demo data.")
    parser.add_argument("--question", action="append", help="Ask one or more custom questions instead of the canned demo prompts.")
    args = parser.parse_args()

    if args.dry_run:
        print(_runtime_summary())
        return 0

    _configure_demo_env(reset=args.reset)
    sys.path.insert(0, str(BACKEND_ROOT))

    from src.config.settings import require_siliconflow_api_key

    require_siliconflow_api_key()

    print("Preparing isolated quickstart runtime...")
    print(_runtime_summary())
    kb, ingested = _load_demo_documents()
    print(f"\nLoaded demo documents into {DEMO_RUNTIME_DIR} ({ingested} new chunks).")

    questions = args.question or DEFAULT_QUESTIONS
    _run_questions(kb, questions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
