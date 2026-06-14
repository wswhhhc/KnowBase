"""离线评估脚本 — 用 rag_eval_dataset.jsonl 回归测试检索+回答质量。

用法：
    uv run python -m src.evaluate

每次评估输出报告到 data/eval_reports/ 目录，同时打印摘要。
"""

import sys
import json
import time
from pathlib import Path
from datetime import UTC, datetime

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ROOT_DIR, require_siliconflow_api_key
from src.knowledge_base import KnowledgeBase
from src.graph import run_query
from src.metrics import log_query

_EVAL_DATASET = ROOT_DIR / "docs" / "rag_eval_dataset.jsonl"
_REPORT_DIR = ROOT_DIR / "data" / "eval_reports"


def load_eval_dataset() -> list[dict]:
    """Load evaluation cases from the JSONL dataset."""
    cases = []
    with open(_EVAL_DATASET, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def evaluate_answer(question: str, answer: str, sources: list[dict], case: dict) -> dict:
    """Score a single answer against the expected evaluation criteria.

    Returns a dict of metric_name -> (score, detail).
    """
    evaluators = case.get("evaluators", [])
    reference_sources = case.get("reference_sources", [])
    expected_answer = case.get("expected_answer", "")

    result: dict[str, tuple[float, str]] = {}

    for ev in evaluators:
        if ev == "groundedness":
            # Check that every source referenced comes from reference_sources
            source_names = {s.get("source", "") for s in sources}
            if not reference_sources:
                score = 1.0 if not source_names else 0.0
                detail = "无引用" if not source_names else f"不应有引用，发现: {source_names}"
            else:
                matched = sum(1 for s in source_names if s in reference_sources)
                score = matched / max(len(reference_sources), 1) if reference_sources else 0.0
                detail = f"来源匹配 {matched}/{len(reference_sources)}"
            result[ev] = (score, detail)

        elif ev == "retrieval_relevance":
            # Simply check if we retrieved anything
            score = 1.0 if sources else 0.0
            detail = f"检索到 {len(sources)} 个来源" if sources else "未检索到来源"
            result[ev] = (score, detail)

        elif ev == "answer_relevance":
            # Check if answer is non-empty and non-boilerplate
            if not answer or len(answer.strip()) < 5:
                score = 0.0
                detail = "回答为空或过短"
            elif "无法回答" in answer or "没有找到" in answer:
                score = 0.0 if reference_sources else 1.0
                detail = "未找到答案" if reference_sources else "正确识别知识库不足"
            else:
                score = 1.0
                detail = "回答非空"
            result[ev] = (score, detail)

        elif ev == "correctness":
            if not expected_answer or not answer:
                score = 0.0
                detail = "缺少预期答案或回答"
            elif "无法回答" in answer or "没有找到" in answer:
                score = 1.0 if not reference_sources else 0.0
                detail = "正确拒绝回答" if not reference_sources else "知识库有相关内容但未回答"
            else:
                # Simple heuristic: check if key terms from expected_answer are present
                key_terms = [t for t in expected_answer.split() if len(t) > 2]
                if not key_terms:
                    score = 0.5
                    detail = "无法评估"
                else:
                    matched = sum(1 for t in key_terms if t in answer)
                    score = matched / len(key_terms)
                    detail = f"关键词匹配 {matched}/{len(key_terms)}"
            result[ev] = (score, detail)

        else:
            result[ev] = (0.0, f"未知评估维度: {ev}")

    return result


def run_evaluation() -> dict:
    """Run full evaluation and return aggregated results."""
    require_siliconflow_api_key()
    kb = KnowledgeBase()
    kb.load_preset_documents()
    cases = load_eval_dataset()

    if not cases:
        print("[评估] 未找到评估数据集 \U0000274c")
        return {}

    print(f"[评估] 加载 {len(cases)} 条评估用例\n")

    all_scores: dict[str, list[float]] = {}
    details: list[dict] = []
    total_elapsed = 0

    for i, case in enumerate(cases, 1):
        qid = case.get("id", f"case_{i}")
        question = case.get("question", "")
        print(f"  [{i}/{len(cases)}] {qid}: {question[:50]}...")

        t0 = time.monotonic()
        try:
            result = run_query(
                question=question,
                thread_id=f"eval_{qid}",
                knowledge_base=kb,
                web_search_enabled=False,
            )
            elapsed = time.monotonic() - t0
            total_elapsed += elapsed

            answer = result.get("answer", "")
            sources = result.get("sources", [])

            scores = evaluate_answer(question, answer, sources, case)
            for metric, (score, detail) in scores.items():
                all_scores.setdefault(metric, []).append(score)

            details.append({
                "id": qid,
                "question": question,
                "answer": answer[:100],
                "elapsed_ms": int(elapsed * 1000),
                "retrieval_count": len(sources),
                "scores": {k: v[0] for k, v in scores.items()},
                "details": {k: v[1] for k, v in scores.items()},
            })

            score_str = " ".join(f"{k}={v[0]:.2f}" for k, v in scores.items())
            print(f"    [{elapsed:.2f}s] {score_str}")

        except Exception as e:
            print(f"    [失败] {e}")
            details.append({
                "id": qid,
                "question": question,
                "error": str(e),
            })

    # Aggregate
    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_cases": len(cases),
        "passed_cases": sum(1 for d in details if "error" not in d),
        "failed_cases": sum(1 for d in details if "error" in d),
        "avg_elapsed_ms": int(total_elapsed / max(len(cases), 1) * 1000),
        "metrics": {},
    }

    for metric, scores in all_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        summary["metrics"][metric] = {
            "avg_score": round(avg, 4),
            "min_score": round(min(scores), 4) if scores else 0,
            "max_score": round(max(scores), 4) if scores else 0,
            "pass_rate": round(sum(1 for s in scores if s >= 0.5) / len(scores), 4) if scores else 0,
        }

    # Save report
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _REPORT_DIR / f"eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {"summary": summary, "details": details}
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'=' * 50}")
    print("[评估报告]")
    print(f"  用例总数: {summary['total_cases']}")
    print(f"  通过: {summary['passed_cases']}  失败: {summary['failed_cases']}")
    print(f"  平均耗时: {summary['avg_elapsed_ms']}ms")
    print(f"  指标:")
    for metric, mdata in summary["metrics"].items():
        print(f"    {metric}: avg={mdata['avg_score']:.2f} pass_rate={mdata['pass_rate']:.0%}")
    print(f"  报告已保存: {report_path}")
    print(f"{'=' * 50}")

    return summary


if __name__ == "__main__":
    run_evaluation()
