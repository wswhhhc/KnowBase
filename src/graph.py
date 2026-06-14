"""LangGraph workflow for routed RAG, conversational memory, and QA checks."""

from __future__ import annotations

from functools import partial
import json
import re
import sqlite3
from typing import Annotated, Iterable, List, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, ValidationError

from config.settings import (
    CHECKPOINT_DB_PATH,
    ENABLE_QUALITY_CHECK,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_RETRIES,
    SCORE_THRESHOLD,
    SILICONFLOW_BASE_URL,
    TOP_K_RERANK,
    TOP_K_RETRIEVAL,
    require_siliconflow_api_key,
)
from src.knowledge_base import KnowledgeBase, RetrievalResult


class GraphState(TypedDict):
    """State shared between LangGraph nodes."""

    question: str
    messages: Annotated[List[BaseMessage], add_messages]
    question_type: str
    rewritten_question: str
    documents: List[RetrievalResult]
    context: str
    answer: str
    sources: List[dict]
    retry_count: int
    retrieval_k: int
    score_threshold: float | None
    quality_ok: bool
    quality_reason: str
    retry_strategy: str


class RerankDecision(BaseModel):
    """Structured rerank result."""

    selected_doc_ids: list[str] = Field(default_factory=list)
    reason: str = ""


class QualityDecision(BaseModel):
    """Structured quality gate result."""

    quality_passed: bool = True
    quality_reason: str = ""
    retry_strategy: Literal["none", "rewrite_query", "expand_retrieval", "insufficient_context"] = "none"


_GRAPH_CACHE: dict[int, object] = {}


def _init_checkpointer():
    """Return a persistent SqliteSaver checkpointer.

    Creates the checkpoint DB on first access. The connection lives for
    the process lifetime; LangGraph handles concurrent writes internally.
    """
    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)


_CHECKPOINTER = _init_checkpointer()


def _get_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        openai_api_key=require_siliconflow_api_key(),
        openai_api_base=SILICONFLOW_BASE_URL,
    )


_SUMMARY_PATTERNS = (
    r"总结", r"概括", r"回顾", r"梳理",
    r"整理.*(对话|聊天|内容|结论)",
)

_MEMORY_PATTERNS = (
    r"上一次.*(问|说|提到|回答)", r"上一轮.*(问|说|提到|回答)",
    r"刚才.*(问|说|提到|回答)", r"刚刚.*(问|说|提到|回答)",
    r"之前.*(问|说|提到|回答)", r"前面.*(问|说|提到|回答)",
    r"上一句.*(问|说|提到|回答)", r"刚那个.*(问题|内容|回答|说法)",
    r"你知道.*上一次.*吗", r"我刚才.*问.*什么",
    r"我刚刚.*问.*什么", r"你刚才.*说.*什么", r"你刚刚.*说.*什么",
)


def detect_question_type(question: str, chat_history: List[tuple[str, str]]) -> str:
    """Regex-based question routing (fallback when LLM classifier is unavailable)."""
    normalized = re.sub(r"\s+", "", question.lower())

    if chat_history:
        if any(re.search(pattern, normalized) for pattern in _SUMMARY_PATTERNS):
            return "conversation_summary"
        if any(re.search(pattern, normalized) for pattern in _MEMORY_PATTERNS):
            return "chat_memory"

    return "knowledge_base"


def route_question(state: GraphState) -> dict:
    """Classify the question using structured LLM routing, with regex fallback."""
    history = _messages_to_turns(state.get("messages", []))

    # Try LLM-based structured classification first
    try:
        llm = _get_llm()
        history_text = _format_chat_history(history, limit=3) if history else "（无历史）"
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是问题分类器。根据用户问题和对话历史，判断意图类型。"
                "只输出 JSON，格式为 {\"question_type\":\"类型\",\"reason\":\"原因\"}。\n\n"
                "类型说明：\n"
                "- knowledge_base：询问知识库内容、技术问题、事实查询。\n"
                "- chat_memory：询问之前的对话内容（如'我刚才问了什么'）。\n"
                "- conversation_summary：要求总结对话（如'总结一下'）。\n"
                "- clarification：问题模糊需要澄清、或纯粹的问候闲聊。",
            ),
            ("human", "对话历史：\n{history}\n\n当前问题：{question}"),
        ])
        result = llm.invoke(
            prompt.format(history=history_text, question=state["question"])
        )
        decision = RouteDecision.model_validate(_json_from_text(str(result.content)))
        return {"question_type": decision.question_type}
    except Exception:
        pass

    # Fallback to regex-based routing
    question_type = detect_question_type(state["question"], history)
    return {"question_type": question_type}


def _messages_to_turns(messages: List[BaseMessage], exclude_last_human: bool = True) -> List[tuple[str, str]]:
    relevant = list(messages)
    if exclude_last_human and relevant and isinstance(relevant[-1], HumanMessage):
        relevant = relevant[:-1]

    turns: list[tuple[str, str]] = []
    pending_question: str | None = None
    for message in relevant:
        if isinstance(message, HumanMessage):
            pending_question = str(message.content)
        elif isinstance(message, AIMessage) and pending_question is not None:
            turns.append((pending_question, str(message.content)))
            pending_question = None
    return turns


def _format_chat_history(history: List[tuple[str, str]], limit: int = 6) -> str:
    recent_turns = history[-limit:]
    return "\n".join(
        f"第{i}轮\n用户：{question}\n助手：{answer}"
        for i, (question, answer) in enumerate(recent_turns, 1)
    )


def _json_from_text(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return json.loads(match.group(0) if match else text)


def parse_rerank_decision(text: str, valid_doc_ids: set[str]) -> RerankDecision:
    """Parse and validate a structured rerank decision."""
    try:
        decision = RerankDecision.model_validate(_json_from_text(text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return RerankDecision(selected_doc_ids=[])

    return RerankDecision(
        selected_doc_ids=[doc_id for doc_id in decision.selected_doc_ids if doc_id in valid_doc_ids],
        reason=decision.reason,
    )


def parse_quality_decision(text: str) -> QualityDecision:
    """Parse a structured quality decision with a conservative fallback."""
    try:
        return QualityDecision.model_validate(_json_from_text(text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        if text.strip().upper().startswith("PASS"):
            return QualityDecision(quality_passed=True, quality_reason="PASS")
        return QualityDecision(
            quality_passed=False,
            quality_reason=text.strip() or "质量检查未返回有效 JSON。",
            retry_strategy="expand_retrieval",
        )


def route_after_classifier(state: GraphState) -> Literal["rewrite_query", "answer_from_history", "summarize_history", "handle_clarification"]:
    question_type = state.get("question_type", "knowledge_base")
    if question_type == "chat_memory":
        return "answer_from_history"
    if question_type == "conversation_summary":
        return "summarize_history"
    if question_type == "clarification":
        return "handle_clarification"
    return "rewrite_query"


def rewrite_query(state: GraphState) -> dict:
    question = state["question"]
    history = _messages_to_turns(state.get("messages", []))

    if not history:
        return {"rewritten_question": question}

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是查询改写助手。结合对话历史，把最新问题改写为独立、完整、适合检索知识库的中文问题。只返回改写后的问题。"),
        ("human", "对话历史：\n{history}\n\n最新问题：{question}"),
    ])
    result = llm.invoke(prompt.format(history=_format_chat_history(history, limit=3), question=question))
    return {"rewritten_question": str(result.content).strip()}


def answer_from_history(state: GraphState) -> dict:
    history = _messages_to_turns(state.get("messages", []))
    if not history:
        answer = "当前会话里还没有可参考的历史消息，所以我无法回答这个问题。"
        return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是对话记忆助手。只能依据给定会话历史回答；如果历史不足，明确说明。用中文回答。"),
        ("human", "会话历史：\n{history}\n\n当前问题：{question}"),
    ])
    result = llm.invoke(prompt.format(history=_format_chat_history(history), question=state["question"]))
    answer = str(result.content).strip()
    return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}


def summarize_history(state: GraphState) -> dict:
    history = _messages_to_turns(state.get("messages", []))
    if not history:
        answer = "当前会话还没有足够内容可供总结。"
        return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是对话总结助手。基于会话历史总结关键信息、结论和未解决问题，不要编造。"),
        ("human", "会话历史：\n{history}\n\n用户要求：{question}"),
    ])
    result = llm.invoke(prompt.format(history=_format_chat_history(history), question=state["question"]))
    answer = str(result.content).strip()
    return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}


def _format_context(results: list[RetrievalResult]) -> tuple[str, list[dict]]:
    context_parts = []
    sources = []
    for index, result in enumerate(results, 1):
        doc = result.document
        source = doc.metadata.get("source", "未知来源")
        chunk_index = doc.metadata.get("chunk_index", "")
        page = doc.metadata.get("page", "")
        loc_parts = [f"来源：{source}"]
        if chunk_index != "":
            loc_parts.append(f"分段：{chunk_index}")
        if page:
            loc_parts.append(f"页码：{page}")
        loc_str = "，".join(loc_parts)
        context_parts.append(
            f"[文档{index}]（ID：{result.chunk_id}，{loc_str}，分数：{result.score:.4f}）\n{doc.page_content}"
        )
        sources.append(
            {
                "index": index,
                "chunk_id": result.chunk_id,
                "source": source,
                "chunk_index": chunk_index,
                "page": page,
                "content": doc.page_content[:300],
                "score": result.score,
                "vector_score": result.vector_score,
                "bm25_score": result.bm25_score,
            }
        )
    return "\n\n".join(context_parts), sources


def retrieve_docs(state: GraphState, kb: KnowledgeBase) -> dict:
    query = state.get("rewritten_question") or state["question"]
    retrieval_k = state.get("retrieval_k") or TOP_K_RETRIEVAL
    score_threshold = state.get("score_threshold", SCORE_THRESHOLD)
    docs = kb.hybrid_search(query, k=retrieval_k, score_threshold=score_threshold)
    context, sources = _format_context(docs)
    return {"documents": docs, "context": context, "sources": sources}


def route_after_retrieval(state: GraphState) -> Literal["rerank_docs", "handle_missing_context"]:
    return "rerank_docs" if state.get("documents") else "handle_missing_context"


def handle_missing_context(state: GraphState) -> dict:
    question = state.get("rewritten_question") or state["question"]
    answer = (
        "知识库里没有找到足够相关的内容来回答这个问题。"
        "你可以换一种问法，补充更具体的关键词，或者上传包含这部分信息的文档后再试。"
        f"\n\n当前问题：{question}"
    )
    return {
        "answer": answer,
        "sources": [],
        "quality_ok": False,
        "quality_reason": "没有检索到相关文档。",
        "retry_strategy": "insufficient_context",
        "messages": [AIMessage(content=answer)],
    }


def handle_clarification(state: GraphState) -> dict:
    """Handle ambiguous or greeting-type queries that need human clarification."""
    question = state["question"]
    answer = (
        f"你问的是「{question}」。这个问题比较模糊，能说得更具体一些吗？"
        "你可以补充具体的关键词，或者描述你想了解的主题。"
    )
    return {
        "answer": answer,
        "sources": [],
        "quality_ok": True,
        "quality_reason": "clarification_response",
        "retry_strategy": "none",
        "messages": [AIMessage(content=answer)],
    }


def rerank_docs(state: GraphState) -> dict:
    docs = state.get("documents", [])
    if not docs:
        return {}

    query = state.get("rewritten_question") or state["question"]
    doc_ids = {result.chunk_id for result in docs}
    docs_text = "\n\n".join(
        f"ID: {result.chunk_id}\n来源: {result.document.metadata.get('source', '未知来源')}\n内容: {result.document.page_content[:500]}"
        for result in docs
    )
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是文档重排器。只输出 JSON，格式为 {{\"selected_doc_ids\":[\"chunk_id\"],\"reason\":\"简短原因\"}}。"),
        ("human", "问题：{query}\n最多选择 {k} 个最相关文档。\n\n候选文档：\n{docs_text}"),
    ])

    try:
        result = llm.invoke(prompt.format(query=query, k=TOP_K_RERANK, docs_text=docs_text))
        decision = parse_rerank_decision(str(result.content), doc_ids)
    except Exception:
        decision = RerankDecision(selected_doc_ids=[])

    by_id = {result.chunk_id: result for result in docs}
    reranked = [by_id[doc_id] for doc_id in decision.selected_doc_ids[:TOP_K_RERANK]]
    if not reranked:
        reranked = docs[:TOP_K_RERANK]

    context, sources = _format_context(reranked)
    return {"documents": reranked, "context": context, "sources": sources}


def generate_answer(state: GraphState) -> dict:
    context = state.get("context", "")
    question = state.get("rewritten_question") or state["question"]

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是知识库问答助手。只能基于参考文档回答；证据不足就说不知道。回答末尾用【来源：文件名·分段号】标注引用位置。用中文回答。"),
        ("human", "参考文档：\n{context}\n\n用户问题：{question}"),
    ])
    result = llm.invoke(prompt.format(context=context, question=question))
    answer = str(result.content).strip()
    return {"answer": answer}


def check_quality(state: GraphState) -> dict:
    if state.get("question_type") != "knowledge_base" or not ENABLE_QUALITY_CHECK:
        answer = state.get("answer", "")
        return {
            "quality_ok": True,
            "quality_reason": "跳过质量检查。",
            "retry_strategy": "none",
            "messages": [AIMessage(content=answer)] if answer else [],
        }

    answer = state.get("answer", "")
    context = state.get("context", "")
    question = state.get("rewritten_question") or state["question"]
    retry_count = state.get("retry_count", 0)

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是回答质量审核员。只输出 JSON，格式为 {{\"quality_passed\": true/false, \"quality_reason\": \"原因\", \"retry_strategy\": \"none|rewrite_query|expand_retrieval|insufficient_context\"}}。"),
        ("human", "问题：{question}\n\n参考文档：{context}\n\n回答：{answer}"),
    ])

    try:
        result = llm.invoke(prompt.format(question=question, context=context[:3000], answer=answer))
        decision = parse_quality_decision(str(result.content))
    except Exception:
        decision = QualityDecision(quality_passed=True, quality_reason="质量检查调用失败，保守放行。")

    update = {
        "quality_ok": decision.quality_passed,
        "quality_reason": decision.quality_reason,
        "retry_strategy": decision.retry_strategy,
        "retry_count": retry_count + 1,
    }
    if decision.quality_passed or retry_count + 1 >= MAX_RETRIES:
        update["messages"] = [AIMessage(content=answer)]
    else:
        strategy = decision.retry_strategy
        if strategy == "expand_retrieval":
            update["retrieval_k"] = min(
                (state.get("retrieval_k") or TOP_K_RETRIEVAL) + TOP_K_RETRIEVAL,
                TOP_K_RETRIEVAL * 4,
            )
            update["score_threshold"] = None
        elif strategy == "rewrite_query":
            # Keep existing retrieval_k but force a re-rewrite
            update["score_threshold"] = None
        # insufficient_context and other unknown strategies go to end via should_retry
    return update


def should_retry(state: GraphState) -> Literal["rewrite_query", "retrieve_docs", "end"]:
    if not state.get("quality_ok", True) and state.get("retry_count", 0) < MAX_RETRIES:
        retry_strategy = state.get("retry_strategy", "expand_retrieval")
        if retry_strategy == "rewrite_query":
            return "rewrite_query"
        return "retrieve_docs"
    return "end"


def build_graph(knowledge_base: KnowledgeBase):
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    workflow.add_node("route_question", route_question)
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("answer_from_history", answer_from_history)
    workflow.add_node("summarize_history", summarize_history)
    workflow.add_node("retrieve_docs", partial(retrieve_docs, kb=knowledge_base))
    workflow.add_node("handle_missing_context", handle_missing_context)
    workflow.add_node("handle_clarification", handle_clarification)
    workflow.add_node("rerank_docs", rerank_docs)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("check_quality", check_quality)

    workflow.set_entry_point("route_question")
    workflow.add_conditional_edges(
        "route_question",
        route_after_classifier,
        {
            "rewrite_query": "rewrite_query",
            "answer_from_history": "answer_from_history",
            "summarize_history": "summarize_history",
            "handle_clarification": "handle_clarification",
        },
    )
    workflow.add_edge("rewrite_query", "retrieve_docs")
    workflow.add_conditional_edges(
        "retrieve_docs",
        route_after_retrieval,
        {"rerank_docs": "rerank_docs", "handle_missing_context": "handle_missing_context"},
    )
    workflow.add_edge("rerank_docs", "generate_answer")
    workflow.add_edge("generate_answer", "check_quality")
    workflow.add_edge("answer_from_history", END)
    workflow.add_edge("summarize_history", END)
    workflow.add_edge("handle_missing_context", END)
    workflow.add_edge("handle_clarification", END)
    workflow.add_conditional_edges("check_quality", should_retry, {"rewrite_query": "rewrite_query", "retrieve_docs": "retrieve_docs", "end": END})

    return workflow.compile(checkpointer=_CHECKPOINTER)


def get_graph(knowledge_base: KnowledgeBase):
    """Return a cached compiled graph for a knowledge base instance."""
    cache_key = id(knowledge_base)
    if cache_key not in _GRAPH_CACHE:
        _GRAPH_CACHE[cache_key] = build_graph(knowledge_base)
    return _GRAPH_CACHE[cache_key]


def _initial_state(question: str) -> GraphState:
    return {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "question_type": "knowledge_base",
        "rewritten_question": "",
        "documents": [],
        "context": "",
        "answer": "",
        "sources": [],
        "retry_count": 0,
        "retrieval_k": TOP_K_RETRIEVAL,
        "score_threshold": SCORE_THRESHOLD,
        "quality_ok": True,
        "quality_reason": "",
        "retry_strategy": "none",
    }


def _graph_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _stream_query(question: str, thread_id: str, knowledge_base: KnowledgeBase) -> Iterable[dict]:
    graph = get_graph(knowledge_base)
    for update in graph.stream(_initial_state(question), config=_graph_config(thread_id), stream_mode="updates"):
        yield update


def run_query(
    question: str,
    thread_id: str,
    knowledge_base: KnowledgeBase,
    *,
    stream: bool = False,
) -> dict | Iterable[dict]:
    """Execute one question against the cached LangGraph workflow."""
    if stream:
        return _stream_query(question, thread_id, knowledge_base)

    graph = get_graph(knowledge_base)
    return graph.invoke(_initial_state(question), config=_graph_config(thread_id))
