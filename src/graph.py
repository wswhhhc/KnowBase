"""LangGraph 工作流定义：查询改写 → 检索 → 重排 → 生成 → 质量检查"""

from typing import List, Tuple, TypedDict, Literal
from functools import partial

from langgraph.graph import StateGraph, END
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from knowledge_base import KnowledgeBase
from config.settings import (
    SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL,
    LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
    TOP_K_RETRIEVAL, TOP_K_RERANK,
    ENABLE_QUALITY_CHECK, MAX_RETRIES,
)


# ---------- 状态定义 ----------

class GraphState(TypedDict):
    """LangGraph 节点间传递的状态"""
    question: str
    rewritten_question: str
    chat_history: List[Tuple[str, str]]
    documents: List[Document]
    context: str
    answer: str
    sources: List[dict]
    retry_count: int
    quality_ok: bool
    quality_ok: bool


# ---------- LLM 初始化 ----------

def _get_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        openai_api_key=SILICONFLOW_API_KEY,
        openai_api_base=SILICONFLOW_BASE_URL,
    )


# ---------- 节点函数 ----------

def rewrite_query(state: GraphState) -> dict:
    """节点1：结合对话历史改写用户问题"""
    question = state["question"]
    history = state.get("chat_history", [])

    if not history:
        return {"rewritten_question": question}

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个查询改写助手。根据对话历史，将用户的最新问题改写为一个独立、完整的问句，使其不依赖上下文也能被理解。直接返回改写后的问句，不要解释。"),
        ("human", "对话历史：\n{history}\n\n最新问题：{question}"),
    ])
    history_text = "\n".join([f"用户：{q}\n助手：{a}" for q, a in history[-3:]])
    result = llm.invoke(prompt.format(history=history_text, question=question))
    return {"rewritten_question": result.content.strip()}


def retrieve_docs(state: GraphState, kb: KnowledgeBase) -> dict:
    """节点2：混合检索"""
    query = state.get("rewritten_question") or state["question"]
    docs = kb.hybrid_search(query, k=TOP_K_RETRIEVAL)

    context_parts = []
    sources = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知来源")
        context_parts.append(f"[文档{i}]（来源：{source}）\n{doc.page_content}")
        sources.append({"index": i, "source": source, "content": doc.page_content[:200]})

    return {
        "documents": docs,
        "context": "\n\n".join(context_parts),
        "sources": sources,
    }


def rerank_docs(state: GraphState) -> dict:
    """节点3：基于 LLM 的精排"""
    docs = state.get("documents", [])
    if not docs:
        return {}

    query = state.get("rewritten_question") or state["question"]

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个文档排序专家。给定一个问题和多个文档片段，请判断每个文档与问题的相关性，"
         "输出最相关的 {k} 个文档编号（按相关性从高到低），每个编号一行。只输出编号，不要其他内容。"),
        ("human", "问题：{query}\n\n{docs_text}"),
    ])

    docs_text = "\n".join([
        f"[文档{i}] {d.page_content[:300]}" for i, d in enumerate(docs, 1)
    ])

    try:
        result = llm.invoke(prompt.format(
            query=query, docs_text=docs_text, k=TOP_K_RERANK
        ))
        selected_indices = []
        for line in result.content.strip().split("\n"):
            line = line.strip()
            if line.isdigit():
                idx = int(line) - 1
                if 0 <= idx < len(docs):
                    selected_indices.append(idx)

        if selected_indices:
            reranked = [docs[i] for i in selected_indices[:TOP_K_RERANK]]
            context_parts = []
            sources = []
            for i, doc in enumerate(reranked, 1):
                source = doc.metadata.get("source", "未知来源")
                context_parts.append(f"[文档{i}]（来源：{source}）\n{doc.page_content}")
                sources.append({"index": i, "source": source, "content": doc.page_content[:200]})

            return {"documents": reranked, "context": "\n\n".join(context_parts), "sources": sources}
    except Exception:
        pass

    return {}


def generate_answer(state: GraphState) -> dict:
    """节点4：LLM 生成回答"""
    context = state.get("context", "")
    question = state.get("rewritten_question") or state["question"]

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个知识库问答助手。请基于以下提供的文档内容回答用户问题。\n"
         "要求：\n"
         "1. 如果文档内容足够，给出详细、准确的回答\n"
         "2. 在回答末尾标注引用来源，格式为【来源：文件名】\n"
         "3. 如果文档内容不足以回答问题，诚实地说你不知道，不要编造\n"
         "4. 用中文回答"),
        ("human", "参考文档：\n{context}\n\n用户问题：{question}"),
    ])

    result = llm.invoke(prompt.format(context=context, question=question))
    return {"answer": result.content.strip()}


def check_quality(state: GraphState) -> dict:
    """节点5：质量检查（检测幻觉、是否回答了问题）"""
    if not ENABLE_QUALITY_CHECK:
        return {"quality_ok": True, "retry_count": state.get("retry_count", 0) + 1}

    answer = state.get("answer", "")
    context = state.get("context", "")
    question = state.get("rewritten_question") or state["question"]
    retry_count = state.get("retry_count", 0)

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个回答质量审核员。检查回答是否存在以下问题：\n"
         "1. 回答是否直接回答了用户问题（而不是回避或说不知道）\n"
         "2. 回答中的信息是否有文档依据（没有编造内容）\n"
         "3. 是否有明显的格式问题\n\n"
         "如果所有检查通过，输出：PASS\n"
         "如果有问题，输出需要改进的具体描述。"),
        ("human", "问题：{question}\n\n参考文档：{context}\n\n回答：{answer}"),
    ])

    try:
        result = llm.invoke(prompt.format(
            question=question, context=context[:1000], answer=answer
        ))
        quality_ok = result.content.strip().upper().startswith("PASS")
    except Exception:
        quality_ok = True

    return {"quality_ok": quality_ok, "retry_count": retry_count + 1}


def should_retry(state: GraphState) -> Literal["retrieve_docs", "end"]:
    """条件边：判断是否需要重试"""
    quality_ok = state.get("quality_ok", True)
    retry_count = state.get("retry_count", 0)

    if not quality_ok and retry_count < MAX_RETRIES:
        return "retrieve_docs"
    return "end"


# ---------- 构建 LangGraph ----------

def build_graph(knowledge_base: KnowledgeBase):
    """构建 LangGraph 工作流"""
    workflow = StateGraph(GraphState)

    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("retrieve_docs", partial(retrieve_docs, kb=knowledge_base))
    workflow.add_node("rerank_docs", rerank_docs)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("check_quality", check_quality)

    workflow.set_entry_point("rewrite_query")
    workflow.add_edge("rewrite_query", "retrieve_docs")
    workflow.add_edge("retrieve_docs", "rerank_docs")
    workflow.add_edge("rerank_docs", "generate_answer")
    workflow.add_edge("generate_answer", "check_quality")

    workflow.add_conditional_edges(
        "check_quality",
        should_retry,
        {"retrieve_docs": "retrieve_docs", "end": END},
    )

    return workflow.compile()


def run_query(
    question: str,
    chat_history: List[Tuple[str, str]],
    knowledge_base: KnowledgeBase,
) -> dict:
    """执行一次问答查询（LangGraph 入口）"""
    graph = build_graph(knowledge_base)

    initial_state: GraphState = {
        "question": question,
        "rewritten_question": "",
        "chat_history": chat_history,
        "documents": [],
        "context": "",
        "answer": "",
        "sources": [],
        "retry_count": 0,
        "quality_ok": True,
    }

    return graph.invoke(initial_state)
