"""Answer generation nodes."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from src.graph import utils as gu
from src.graph.state import GraphState, GraphStateUpdate


def generate_answer(state: GraphState) -> GraphStateUpdate:
    context = state.get("context", "")
    web_context = state.get("web_context", "")
    web_search_error = state.get("web_search_error", "")
    question = state.get("rewritten_question") or state["question"]
    used_web_search = state.get("used_web_search", False)
    history = gu._messages_to_turns(state.get("messages", []))
    strategy = state.get("search_strategy", "balanced")

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
        system_msg += "参考文档涵盖了全文多个部分，请综合回答。"
    if used_web_search and web_context:
        system_msg += "可以基于工作区和网络搜索结果回答。在回答中引用来源时，使用 [1]、[2] 等编号标注，编号对应参考文档列表中的顺序。多个引用用逗号分隔如 [1,2]。用中文回答。保持与对话历史中已给出信息的一致性，如果同一实体已有过描述，不要自相矛盾。"
    else:
        system_msg += "只能基于参考文档回答；证据不足就说不知道。在回答中引用参考文档时，使用 [1]、[2] 等编号标注来源，编号对应上方参考文档列表中的编号。例如：根据文档说明，该值为 42[1]。多个引用用逗号分隔如 [1,2]。每个关键事实都应标注来源。用中文回答。保持与对话历史中已给出信息的一致性，如果同一实体已有过描述，不要自相矛盾。"

    llm = gu._get_llm()
    if history:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "对话历史：\n{history}\n\n参考文档：\n{context}\n\n用户问题：{question}"),
        ])
        result = llm.invoke(prompt.format(history=gu._format_chat_history(history, limit=3), context=context, question=question))
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "参考文档：\n{context}\n\n用户问题：{question}"),
        ])
        result = llm.invoke(prompt.format(context=context, question=question))
    answer = str(result.content).strip()

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
        **gu.extract_token_usage(result),
    }
