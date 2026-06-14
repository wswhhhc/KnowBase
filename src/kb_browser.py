"""知识库内容浏览页面 — Streamlit 子页面。"""

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx


def show(kb):
    """Render the knowledge base content browser."""
    st.subheader("📖 知识库内容浏览")

    if kb.document_count == 0:
        st.info("知识库为空，请先上传文档。")
        if st.button("← 返回对话"):
            st.session_state.show_browser = False
            st.rerun()
        return

    # 统计
    col1, col2, col3 = st.columns(3)
    col1.metric("文档片段总数", kb.document_count)
    col2.metric("来源文件数", len(kb.source_counts()))
    unique_chars = sum(len(d.page_content) for d in kb.all_docs)
    col3.metric("总字符数", unique_chars)

    st.divider()

    # 搜索
    search_query = st.text_input("🔍 搜索文档内容（关键词，空格分隔）", placeholder="输入关键词搜索...")
    if search_query:
        results = kb.search_content(search_query)
        st.caption(f"找到 {len(results)} 个匹配片段")
        display_docs = results
    else:
        display_docs = kb.all_docs

    # 来源筛选
    sources = [s for s, _c in kb.source_counts()]
    selected_source = st.selectbox(
        "按来源筛选",
        options=["全部"] + sorted(sources),
    )

    if selected_source != "全部":
        display_docs = [
            d for d in display_docs
            if d.metadata.get("source", "") == selected_source
        ]

    # 显示文档
    if not display_docs:
        st.info("没有匹配的内容。")
        if st.button("← 返回对话", key="back_empty"):
            st.session_state.show_browser = False
            st.rerun()
        return

    for i, doc in enumerate(display_docs):
        source = doc.metadata.get("source", "未知来源")
        chunk_index = doc.metadata.get("chunk_index", "")
        chunk_id = doc.metadata.get("chunk_id", "")
        page = doc.metadata.get("page", "")
        preview = doc.page_content[:500]

        with st.expander(f"📄 [{source}] #{chunk_index or ''} ({len(doc.page_content)}字)", expanded=(i == 0 and len(display_docs) == 1)):
            meta_parts = []
            if source:
                meta_parts.append(f"**来源：** {source}")
            if chunk_index != "":
                meta_parts.append(f"**分段：** {chunk_index}")
            if page:
                meta_parts.append(f"**页码：** {page}")
            if chunk_id:
                meta_parts.append(f"**ID：** `{chunk_id[:24]}...`")
            if meta_parts:
                st.caption(" | ".join(meta_parts))

            st.text(preview)
            if len(doc.page_content) > 500:
                st.caption(f"... 还有 {len(doc.page_content) - 500} 个字")

    st.divider()
    if st.button("← 返回对话"):
        st.session_state.show_browser = False
        st.rerun()
