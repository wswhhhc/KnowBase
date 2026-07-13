"""Answer generation nodes."""

import logging
import re

from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

from src.graph import utils as gu
from src.graph.state import GraphState, GraphStateUpdate


logger = logging.getLogger(__name__)

_STANDARD_GENERATION_DEADLINE_SECONDS = 15
_DEEP_GENERATION_DEADLINE_SECONDS = 20
_DEEP_REASONING_RE = re.compile(
    r"(?:综合|比较|分析|权衡|推导|评估|方案|风险|影响|全文|多角度|步骤|因果|趋势)"
)


def _requires_deep_reasoning(question: str) -> bool:
    normalized = re.sub(r"\s+", "", question)
    return len(normalized) >= 60 or bool(_DEEP_REASONING_RE.search(normalized))


def generate_answer(state: GraphState, config: RunnableConfig | None = None) -> GraphStateUpdate:
    context = state.get("context", "")
    web_context = state.get("web_context", "")
    web_search_error = state.get("web_search_error", "")
    question = state.get("rewritten_question") or state["question"]
    used_web_search = state.get("used_web_search", False)
    history = gu._messages_to_turns(state.get("messages", []))
    strategy = state.get("search_strategy", "balanced")
    token_callback = gu.get_stream_token_callback(config)

    if web_context:
        context = f"{context}\n\n{web_context}" if context else web_context
    elif used_web_search and web_search_error and not context:
        answer = (
            "工作区里没有找到足够相关的内容，联网搜索也没有可用结果。"
            f"\n\n联网搜索状态：{web_search_error}"
        )
        return {
            "answer": answer,
            "sources": [],
            "quality_ok": False,
            "quality_reason": web_search_error,
        }

    system_msg = "你是工作区问答助手。"
    if strategy == "deep" and not (used_web_search and web_context):
        system_msg += (
            "参考文档涵盖了全文多个部分，请综合回答，但优先采用直接回答问题的明确证据。"
            "不要把同一团队中的相关实体自动归入问题所问类别；文档表述冲突时，应说明差异并以最直接的证据为准。"
        )
    if used_web_search and web_context:
        system_msg += "可以基于工作区和网络搜索结果回答。在回答中引用来源时，使用 [1]、[2] 等编号标注，编号对应参考文档列表中的顺序。多个引用用逗号分隔如 [1,2]。用中文回答。保持与对话历史中已给出信息的一致性，如果同一实体已有过描述，不要自相矛盾。"
    else:
        system_msg += "只能基于参考文档回答；证据不足就说不知道。在回答中引用参考文档时，使用 [1]、[2] 等编号标注来源，编号对应上方参考文档列表中的编号。例如：根据文档说明，该值为 42[1]。多个引用用逗号分隔如 [1,2]。每个关键事实都应标注来源。用中文回答。保持与对话历史中已给出信息的一致性，如果同一实体已有过描述，不要自相矛盾。"

    reasoning_mode = (
        "deep"
        if strategy == "deep" and _requires_deep_reasoning(question)
        else "standard"
    )
    llm = gu._get_llm(streaming=True, reasoning_mode=reasoning_mode)
    if history:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "对话历史：\n{history}\n\n参考文档：\n{context}\n\n用户问题：{question}"),
        ])
        formatted_prompt = prompt.format(
            history=gu._format_chat_history(history, limit=3),
            context=context,
            question=question,
        )
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "参考文档：\n{context}\n\n用户问题：{question}"),
        ])
        formatted_prompt = prompt.format(context=context, question=question)

    deadline_seconds = (
        _DEEP_GENERATION_DEADLINE_SECONDS
        if reasoning_mode == "deep"
        else _STANDARD_GENERATION_DEADLINE_SECONDS
    )
    try:
        answer, token_usage = gu.run_llm_text(
            llm,
            formatted_prompt,
            stream=True,
            token_callback=None,
            deadline_seconds=deadline_seconds,
            allow_partial_on_deadline=False,
        )
    except Exception as exc:
        if reasoning_mode != "deep":
            raise
        logger.warning("深度生成超出时限，回退到标准生成: %s", exc)
        fallback_llm = gu._get_llm(streaming=True, reasoning_mode="standard")
        answer, token_usage = gu.run_llm_text(
            fallback_llm,
            formatted_prompt,
            stream=True,
            token_callback=None,
            deadline_seconds=_STANDARD_GENERATION_DEADLINE_SECONDS,
            allow_partial_on_deadline=False,
        )
    if callable(token_callback) and answer:
        token_callback(answer)

    sources = state.get("sources", [])
    if web_context:
        sources = sources + [
            {
                "index": len(sources) + i,
                "chunk_id": item.get("url", ""),
                "source": item.get("title") or item.get("url") or "网络来源",
                "chunk_index": None,
                "page": None,
                "content": item.get("content", "")[:300],
                "score": item.get("score"),
                "vector_score": None,
                "bm25_score": None,
                "url": item.get("url", ""),
            }
            for i, item in enumerate(state.get("web_search_results", []), 1)
        ]
    return {
        "answer": answer,
        "sources": sources,
        **token_usage,
    }
