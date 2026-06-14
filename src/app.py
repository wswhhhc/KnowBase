"""KnowBase — Streamlit Web 主入口"""

import sys
from pathlib import Path

# 确保项目根目录和 src 目录在 Python 路径中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st
from pathlib import Path

from src.knowledge_base import KnowledgeBase
from src.graph import run_query
from src.utils import save_uploaded_file, format_chat_history
from config.settings import DATA_DIR


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
    count = kb.load_preset_documents()
    return kb, count


if "messages" not in st.session_state:
    st.session_state.messages = []

if "kb_ready" not in st.session_state:
    with st.spinner("正在加载知识库..."):
        kb, doc_count = init_knowledge_base()
        st.session_state.kb = kb
        st.session_state.doc_count = doc_count
        st.session_state.kb_ready = True


# ---------- 侧边栏 ----------

with st.sidebar:
    st.header("知识库管理")

    if st.session_state.kb_ready:
        st.success(f"预设文档已加载：{st.session_state.doc_count} 个片段")

    st.divider()
    st.subheader("上传文档")

    uploaded_file = st.file_uploader(
        "选择文件（.txt / .md）",
        type=["txt", "md"],
        accept_multiple_files=False,
    )

    if uploaded_file and st.button("添加到知识库", use_container_width=True):
        file_path = save_uploaded_file(uploaded_file)
        with st.spinner(f"正在处理: {uploaded_file.name}..."):
            try:
                chunk_count = st.session_state.kb.add_document(file_path)
                st.session_state.doc_count += chunk_count
                st.success(f"✅ {uploaded_file.name} 已入库（{chunk_count} 个片段）")
                st.rerun()
            except Exception as e:
                st.error(f"处理失败: {e}")

    if st.session_state.doc_count > 0:
        st.divider()
        if st.button("🗑️ 清空知识库", use_container_width=True, type="secondary"):
            st.session_state.kb.clear()
            st.session_state.doc_count = 0
            st.session_state.messages = []
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
                    st.caption(f"**{s['source']}**")
                    st.text(s["content"][:300] + ("..." if len(s["content"]) > 300 else ""))

# 输入框
if prompt := st.chat_input("请输入你的问题..."):
    # 显示用户消息
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 检查知识库状态
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
                chat_history = format_chat_history(st.session_state.messages[:-1])
                result = run_query(
                    question=prompt,
                    chat_history=chat_history,
                    knowledge_base=st.session_state.kb,
                )
                answer = result.get("answer", "抱歉，我无法回答这个问题。")
                sources = result.get("sources", [])

                st.markdown(answer)
                if sources:
                    with st.expander("📎 引用来源"):
                        for s in sources:
                            st.caption(f"**{s['source']}**")
                            st.text(s["content"][:300] + ("..." if len(s["content"]) > 300 else ""))

                # 保存到历史
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })

            except Exception as e:
                error_msg = f"出错了: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })
