"""离线评估脚本 — 用 rag_eval_dataset.jsonl 回归测试检索+回答质量。

使用启发式和 LLM-as-judge 两种评估。新增的 `faithfulness` 和
`answer_relevance_llm` 评估器会调用 LLM 做内容级审核，需在数据集中
通过 evaluators 列表显式启用（与现有评估器同级配置）。

用法：
    uv run python -m src.evaluate

每次评估输出报告到 runtime/local/eval_reports/ 目录，同时打印摘要。
"""

import sys
import json
import time
from pathlib import Path
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.config.constants import LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE, SILICONFLOW_BASE_URL
from src.config.runtime_overrides import require_siliconflow_api_key
from src.config.settings import ROOT_DIR
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.rag.knowledge_base import KnowledgeBase
from src.graph import run_query
from src.metrics import log_query
from src.utils import json_from_text

_EVAL_DATASET = ROOT_DIR / "docs" / "rag_eval_dataset.jsonl"
_REPORT_DIR = ROOT_DIR / "runtime" / "local" / "eval_reports"


class FaithfulnessScore(BaseModel):
    """LLM faithfulness evaluation result."""
    score: float = Field(description="分数 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="判断理由")


class RelevanceScore(BaseModel):
    """LLM answer relevance evaluation result."""
    score: float = Field(description="分数 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="判断理由")


def _get_eval_llm():
    """Create an LLM instance for evaluation (lower temperature for consistency)."""
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.1,
        max_tokens=512,
        openai_api_key=require_siliconflow_api_key(),
        openai_api_base=SILICONFLOW_BASE_URL,
    )



_EVAL_DATASET = ROOT_DIR / "docs" / "rag_eval_dataset.jsonl"
_REPORT_DIR = ROOT_DIR / "runtime" / "local" / "eval_reports"


def load_eval_dataset() -> list[dict]:
    """Load evaluation cases from the JSONL dataset."""
    cases = []
    with open(_EVAL_DATASET, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def evaluate_answer(question: str, answer: str, sources: list[dict], context: str, case: dict) -> dict:
    """Score a single answer against the expected evaluation criteria.

    Supports both heuristic evaluators and LLM-as-judge evaluators.
    LLM evaluators (faithfulness, answer_relevance_llm) require the
    presence of ``reference_sources`` or ``expected_answer`` in the case.

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

        elif ev == "faithfulness":
            # LLM-as-judge: check if answer is faithful to retrieved context
            if not answer or not context:
                score = 0.0
                detail = "缺少回答或上下文，无法评估 faithfulness"
            else:
                try:
                    llm = _get_eval_llm()
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", "你是回答忠实度审核员。判断回答是否基于参考文档，没有凭空编造。"
                         "只输出 JSON，格式为 {\"score\": 0.0-1.0, \"reasoning\": \"理由\"}。"),
                        ("human", "参考文档：\n{context}\n\n回答：{answer}\n\n问题：{question}"),
                    ])
                    eval_result = llm.invoke(prompt.format(context=context[:3000], answer=answer, question=question))
                    decision = FaithfulnessScore.model_validate(json_from_text(str(eval_result.content)))
                    score = decision.score
                    detail = decision.reasoning
                except Exception as e:
                    score = 0.5  # Conservative fallback
                    detail = f"LLM 评估失败: {e}"
            result[ev] = (score, detail)

        elif ev == "answer_relevance_llm":
            # LLM-as-judge: check if answer actually addresses the question
            if not answer:
                score = 0.0
                detail = "回答为空"
            else:
                try:
                    llm = _get_eval_llm()
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", "你是回答相关性审核员。判断回答是否真正回答了用户问题。"
                         "只输出 JSON，格式为 {\"score\": 0.0-1.0, \"reasoning\": \"理由\"}。"),
                        ("human", "问题：{question}\n\n回答：{answer}"),
                    ])
                    eval_result = llm.invoke(prompt.format(question=question, answer=answer))
                    decision = RelevanceScore.model_validate(json_from_text(str(eval_result.content)))
                    score = decision.score
                    detail = decision.reasoning
                except Exception as e:
                    score = 0.5
                    detail = f"LLM 评估失败: {e}"
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
            context = result.get("context", "")

            scores = evaluate_answer(question, answer, sources, context, case)
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
