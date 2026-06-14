"""KnowBase — Streamlit Web 主入口"""

import sys
from uuid import uuid4
from pathlib import Path

# 确保项目根目录和 src 目录在 Python 路径中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from src.knowledge_base import KnowledgeBase
from src.graph import run_query
from src.utils import save_uploaded_file


# ---------- 页面配置 ----------

st.set_page_config(
    page_title="KnowBase - 知识库问答助手",
    page_icon="📚",
    layout="wide",
)

st.title("📚 KnowBase 知识库问答助手")


# ---------- 初始化 ----------

@st.cache_resource
def init_knowledge_base():
    """初始化知识库（仅一次）"""
    kb = KnowledgeBase()
    kb.load_preset_documents()
    return kb, kb.document_count


if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid4())

if "kb_ready" not in st.session_state:
    with st.spinner("正在加载知识库..."):
        try:
            kb, doc_count = init_knowledge_base()
            st.session_state.kb = kb
            st.session_state.doc_count = doc_count
            st.session_state.kb_ready = True
            st.session_state.kb_error = ""
        except Exception as e:
            st.session_state.kb_ready = False
            st.session_state.doc_count = 0
            st.session_state.kb_error = str(e)


# ---------- 侧边栏 ----------

with st.sidebar:
    st.header("知识库管理")

    if st.session_state.kb_ready:
        st.success(f"知识库已加载：{st.session_state.doc_count} 个片段")
        source_counts = st.session_state.kb.source_counts()
        if source_counts:
            with st.expander("已入库来源", expanded=True):
                for source, count in source_counts:
                    st.caption(f"{source}：{count} 个片段")
    else:
        st.error(f"知识库加载失败：{st.session_state.kb_error}")

    st.divider()
    st.subheader("上传文档")

    uploaded_file = st.file_uploader(
        "选择文件（.txt / .md）",
        type=["txt", "md"],
        accept_multiple_files=False,
        disabled=not st.session_state.kb_ready,
    )

    if uploaded_file and st.button(
        "添加到知识库",
        use_container_width=True,
        disabled=not st.session_state.kb_ready,
    ):
        with st.spinner(f"正在处理: {uploaded_file.name}..."):
            try:
                file_path = save_uploaded_file(uploaded_file)
                chunk_count = st.session_state.kb.ingest_file(file_path, source_name=Path(file_path).name)
                st.session_state.doc_count = st.session_state.kb.document_count
                st.success(f"✅ {uploaded_file.name} 已入库（{chunk_count} 个片段）")
                st.rerun()
            except Exception as e:
                st.error(f"处理失败: {e}")

    if st.session_state.kb_ready and st.session_state.doc_count > 0:
        st.divider()
        if st.button("🗑️ 清空知识库", use_container_width=True, type="secondary"):
            st.session_state.kb.clear()
            st.session_state.doc_count = 0
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid4())
            st.rerun()

    st.divider()
    st.caption(f"知识库状态: {st.session_state.doc_count} 个文档片段")

    with st.expander("关于 KnowBase"):
        st.markdown("""
        **KnowBase** 基于 LangChain + LangGraph 构建。

        问答流程：
        1. 查询改写 — 结合对话历史优化问题
        2. 混合检索 — 向量检索 + BM25
        3. 重排序 — LLM 精排
        4. 生成回答 — LLM 带上下文生成
        5. 质量检查 — 自动评估质量，不合格重试
        """)


# ---------- 主界面：对话区 ----------

# 显示对话历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander("📎 引用来源"):
                for s in msg["sources"]:
                    score_text = f" · score={s.get('score', 0):.4f}" if s.get("score") is not None else ""
                    st.caption(f"**{s['source']}**{score_text}")
                    st.text(s["content"][:300] + ("..." if len(s["content"]) > 300 else ""))
        if msg.get("quality_reason"):
            st.caption(f"质量检查：{msg['quality_reason']}")

# 输入框
if prompt := st.chat_input("请输入你的问题..."):
    # 显示用户消息
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 检查知识库状态
    if not st.session_state.kb_ready:
        with st.chat_message("assistant"):
            st.error(f"知识库加载失败：{st.session_state.kb_error}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"知识库加载失败：{st.session_state.kb_error}",
        })
        st.rerun()

    if st.session_state.doc_count == 0:
        with st.chat_message("assistant"):
            st.error("知识库为空！请先上传文档或确认预设文档已加载。")
        st.session_state.messages.append({
            "role": "assistant",
            "content": "知识库为空，请先通过侧边栏上传文档。",
        })
        st.rerun()

    # 调用 LangGraph 工作流
    with st.chat_message("assistant"):
        with st.spinner("正在思考..."):
            try:
                progress_placeholder = st.empty()
                answer = ""
                sources = []
                quality_reason = ""
                node_labels = {
                    "route_question": "问题路由",
                    "rewrite_query": "查询改写",
                    "retrieve_docs": "混合检索",
                    "rerank_docs": "结构化重排",
                    "generate_answer": "生成回答",
                    "check_quality": "质量检查",
                    "answer_from_history": "会话记忆",
                    "summarize_history": "会话总结",
                    "handle_missing_context": "证据不足兜底",
                }

                events = run_query(
                    question=prompt,
                    thread_id=st.session_state.thread_id,
                    knowledge_base=st.session_state.kb,
                    stream=True,
                )

                for event in events:
                    for node_name, update in event.items():
                        progress_placeholder.caption(f"正在执行：{node_labels.get(node_name, node_name)}")
                        if isinstance(update, dict):
                            answer = update.get("answer", answer)
                            sources = update.get("sources", sources)
                            quality_reason = update.get("quality_reason", quality_reason)

                progress_placeholder.empty()
                answer = answer or "抱歉，我无法回答这个问题。"

                st.markdown(answer)
                if sources:
                    with st.expander("📎 引用来源"):
                        for s in sources:
                            score_text = f" · score={s.get('score', 0):.4f}" if s.get("score") is not None else ""
                            st.caption(f"**{s['source']}**{score_text}")
                            st.text(s["content"][:300] + ("..." if len(s["content"]) > 300 else ""))
                if quality_reason:
                    st.caption(f"质量检查：{quality_reason}")

                # 保存到历史
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "quality_reason": quality_reason,
                })

            except Exception as e:
                error_msg = f"出错了: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })
