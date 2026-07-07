"""History-backed graph nodes."""

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from src.graph import utils as gu
from src.graph.state import GraphState, GraphStateUpdate


def answer_from_history(state: GraphState, config: RunnableConfig | None = None) -> GraphStateUpdate:
    history = gu._messages_to_turns(state.get("messages", []))
    if not history:
        answer = "当前会话里还没有可参考的历史消息，所以我无法回答这个问题。"
        return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}

    llm = gu._get_llm(streaming=True)
    token_callback = gu.get_stream_token_callback(config)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是对话记忆助手。只能依据给定会话历史回答；如果历史不足，明确说明。用中文回答。"),
        ("human", "会话历史：\n{history}\n\n当前问题：{question}"),
    ])
    answer, token_usage = gu.run_llm_text(
        llm,
        prompt.format(history=gu._format_chat_history(history), question=state["question"]),
        stream=True,
        token_callback=token_callback,
    )
    return {
        "answer": answer,
        "sources": [],
        "messages": [AIMessage(content=answer)],
        **token_usage,
    }


def summarize_history(state: GraphState, config: RunnableConfig | None = None) -> GraphStateUpdate:
    history = gu._messages_to_turns(state.get("messages", []))
    if not history:
        answer = "当前会话还没有足够内容可供总结。"
        return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}

    llm = gu._get_llm(streaming=True)
    token_callback = gu.get_stream_token_callback(config)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是对话总结助手。基于会话历史总结关键信息、结论和未解决问题，不要编造。"),
        ("human", "会话历史：\n{history}\n\n用户要求：{question}"),
    ])
    answer, token_usage = gu.run_llm_text(
        llm,
        prompt.format(history=gu._format_chat_history(history), question=state["question"]),
        stream=True,
        token_callback=token_callback,
    )
    return {
        "answer": answer,
        "sources": [],
        "messages": [AIMessage(content=answer)],
        **token_usage,
    }
