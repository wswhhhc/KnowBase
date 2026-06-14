"""KnowBase — Streamlit Web 主入口"""

import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from config.settings import ROOT_DIR
from src.conversations import (
    init_db,
    create_conversation,
    list_conversations,
    get_conversation,
    update_title,
    delete_conversation,
    add_message,
    get_messages,
    update_feedback,
    export_conversation,
)
from langchain_core.messages import AIMessageChunk
from src.knowledge_base import KnowledgeBase
from src.graph import run_query
from src.utils import save_uploaded_file
from src.metrics import log_query

# ---------- DB init ----------
init_db()

# ---------- 页面配置 ----------

st.set_page_config(
    page_title="KnowBase - 知识库问答助手",
    page_icon="📚",
    layout="wide",
)

st.title("📚 KnowBase 知识库问答助手")


# ---------- 初始化 ----------

_THREAD_ID_FILE = ROOT_DIR / "data" / ".thread_id"


def _load_or_create_thread_id() -> str:
    try:
        if _THREAD_ID_FILE.exists():
            tid = _THREAD_ID_FILE.read_text(encoding="utf-8").strip()
            if tid:
                return tid
    except OSError:
        pass
    tid = str(uuid4())
    try:
        _THREAD_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _THREAD_ID_FILE.write_text(tid, encoding="utf-8")
    except OSError:
        pass
    return tid


@st.cache_resource
def init_knowledge_base():
    kb = KnowledgeBase()
    kb.load_preset_documents()
    return kb, kb.document_count


# --- session state ---

for key, default in [
    ("messages", []),
    ("thread_id", _load_or_create_thread_id()),
    ("kb_ready", False),
    ("doc_count", 0),
    ("kb_error", ""),
    ("show_browser", False),
    ("current_conv_id", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if "kb" not in st.session_state:
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


# ==========================
# 侧边栏
# ==========================

with st.sidebar:
    # ---------- 对话管理 ----------
    st.header("💬 对话")

    conversations = list_conversations()

    # 新建对话
    if st.button("➕ 新对话", use_container_width=True, type="primary"):
        conv = create_conversation()
        st.session_state.current_conv_id = conv["id"]
        st.session_state.messages = []
        st.session_state.thread_id = conv["thread_id"]
        st.rerun()

    # 对话列表
    conv_options = {c["id"]: c["title"] for c in conversations}
    current_id = st.session_state.get("current_conv_id")

    if conv_options:
        # 计算选中项索引
        idx_options = list(conv_options.keys())
        default_idx = idx_options.index(current_id) if current_id in idx_options else 0
        selected_id = st.selectbox(
            "切换对话",
            options=idx_options,
            format_func=lambda x: conv_options[x][:40] + ("..." if len(conv_options[x]) > 40 else ""),
            index=default_idx,
            label_visibility="collapsed",
        )

        # 切换对话时加载历史
        if selected_id != current_id:
            st.session_state.current_conv_id = selected_id
            conv = get_conversation(selected_id)
            st.session_state.thread_id = conv["thread_id"] if conv else str(uuid4())
            msgs = get_messages(selected_id)
            st.session_state.messages = [
                {
                    "role": m["role"],
                    "content": m["content"],
                    "sources": m.get("sources", []),
                    "quality_reason": m.get("quality_reason", ""),
                    "_feedback": m.get("feedback"),
                    "_db_id": m["id"],
                }
                for m in msgs
            ]
            st.rerun()

        # 对话操作
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ 重命名", use_container_width=True, key="rename_btn"):
                st.session_state.show_rename = True
        with col2:
            if st.button("🗑️ 删除", use_container_width=True, key="del_btn"):
                delete_conversation(selected_id)
                st.session_state.current_conv_id = None
                st.session_state.messages = []
                st.session_state.thread_id = str(uuid4())
                st.rerun()

        # 重命名输入
        if st.session_state.get("show_rename"):
            new_title = st.text_input("新名称", value=conv_options[selected_id], key="rename_input")
            if st.button("确认", key="rename_confirm"):
                update_title(selected_id, new_title)
                st.session_state.show_rename = False
                st.rerun()

        # 导出
        export_key = f"export_{selected_id}"
        export_bytes = export_conversation(selected_id).encode("utf-8")
        st.download_button(
            "📥 导出对话",
            data=export_bytes,
            file_name=f"knowbase_conv_{selected_id[:8]}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.caption("暂无对话，点击「新对话」开始")
        # 自动创建第一个对话
        conv = create_conversation()
        st.session_state.current_conv_id = conv["id"]
        st.session_state.thread_id = conv["thread_id"]
        st.rerun()

    st.divider()

    # ---------- 联网搜索开关 ----------
    from config.settings import TAVILY_API_KEY, _is_configured_api_key

    web_search_available = _is_configured_api_key(TAVILY_API_KEY)
    web_search_default = st.session_state.get("web_search_enabled", web_search_available)
    st.session_state.web_search_enabled = st.checkbox(
        "🌐 启用联网搜索",
        value=web_search_default,
        disabled=not web_search_available,
        help=(
            "知识库检索不足时自动联网搜索补充。"
            if web_search_available
            else "未配置 TAVILY_API_KEY，请在 .env 中设置。"
        ),
    )

    st.divider()

    # ---------- 知识库管理 ----------
    st.header("知识库管理")

    if st.session_state.kb_ready:
        st.success(f"已加载：{st.session_state.doc_count} 个片段")
    else:
        st.error(f"加载失败：{st.session_state.kb_error}")
        st.stop()

    # 浏览知识库
    if st.button("📖 浏览知识库", use_container_width=True):
        st.session_state.show_browser = True
        st.rerun()

    st.divider()
    st.subheader("上传文档")

    uploaded_file = st.file_uploader(
        "选择文件（支持 .txt / .md / .pdf / .docx / .html）",
        type=["txt", "md", "pdf", "docx", "html"],
        accept_multiple_files=False,
        key="doc_uploader",
    )

    if uploaded_file and st.button("添加到知识库", use_container_width=True):
        with st.spinner(f"正在处理: {uploaded_file.name}..."):
            try:
                file_path = save_uploaded_file(uploaded_file)
                chunk_count = st.session_state.kb.ingest_file(file_path, source_name=Path(file_path).name)
                st.session_state.doc_count = st.session_state.kb.document_count
                if chunk_count == 0:
                    st.info(f"⏭️ {uploaded_file.name} 已存在")
                else:
                    st.success(f"✅ {uploaded_file.name} 已入库（{chunk_count} 个新片段）")
                st.rerun()
            except Exception as e:
                st.error(f"处理失败: {e}")

    # ---------- URL 导入 ----------
    st.subheader("导入网页")
    url = st.text_input(
        "粘贴网页 URL",
        placeholder="https://example.com/article",
        key="url_input",
    )
    if url and st.button("抓取并导入", use_container_width=True):
        with st.spinner(f"正在抓取: {url}..."):
            try:
                from src.loaders import load_url

                docs = load_url(url)
                source_name = docs[0].metadata.get("title", url) if docs else url
                splits = st.session_state.kb._prepare_splits(docs)
                for split in splits:
                    split.metadata["source"] = source_name[:80]
                new_splits = [
                    s for s in splits
                    if s.metadata["chunk_id"] not in st.session_state.kb.existing_chunk_ids
                ]
                if new_splits:
                    new_ids = [s.metadata["chunk_id"] for s in new_splits]
                    st.session_state.kb.vector_store.add_documents(new_splits, ids=new_ids)
                    st.session_state.kb.all_docs.extend(new_splits)
                    st.session_state.kb._rebuild_indexes()
                    st.session_state.doc_count = st.session_state.kb.document_count
                    st.success(f"✅ {source_name[:40]} 已入库（{len(new_splits)} 个片段）")
                else:
                    st.info(f"⏭️ {source_name[:40]} 内容已存在")
                st.rerun()
            except Exception as e:
                st.error(f"抓取失败: {e}")

    # ---------- 来源管理 ----------
    if st.session_state.kb_ready and st.session_state.doc_count > 0:
        source_counts = st.session_state.kb.source_counts()
        if source_counts:
            st.divider()
            st.subheader("文档来源")
            for source, count in source_counts:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"{source}：{count}")
                with col2:
                    if st.button("删除", key=f"del_{source}", help=f"删除 {source}"):
                        st.session_state.kb.delete_source(source)
                        st.session_state.doc_count = st.session_state.kb.document_count
                        st.rerun()

        st.divider()
        if st.button("🗑️ 清空知识库", use_container_width=True, type="secondary"):
            st.session_state.kb.clear()
            st.session_state.doc_count = 0
            st.session_state.messages = []
            if st.session_state.current_conv_id:
                conv = get_conversation(st.session_state.current_conv_id)
                st.session_state.thread_id = conv["thread_id"] if conv else str(uuid4())
            else:
                st.session_state.thread_id = str(uuid4())
            st.rerun()

    st.divider()
    st.caption(f"状态: {st.session_state.doc_count} 个片段")

    with st.expander("关于 KnowBase"):
        st.markdown("""
        **KnowBase** — LangChain + LangGraph 知识库问答助手。

        问答流程：
        1. 查询改写 — 结合对话历史优化问题
        2. 混合检索 — 向量检索 + BM25
        3. 重排序 — LLM 精排
        4. 生成回答 — LLM 带上下文生成
        5. 质量检查 — 不足时自动联网搜索补充
        """)


# ==========================
# 主界面
# ==========================

# 知识库浏览模式
if st.session_state.get("show_browser"):
    from src.kb_browser import show as show_browser

    show_browser(st.session_state.kb)
    st.stop()

# 显示对话历史
for msg_idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander("📎 引用来源"):
                for s in msg["sources"]:
                    score_text = f" · score={s.get('score', 0):.4f}" if s.get("score") is not None else ""
                    loc_parts = []
                    if s.get("chunk_index"):
                        loc_parts.append(f"分段 #{s['chunk_index']}")
                    if s.get("page"):
                        loc_parts.append(f"第 {s['page']} 页")
                    loc_text = f"（{', '.join(loc_parts)}）" if loc_parts else ""
                    st.caption(f"**{s['source']}**{loc_text}{score_text}")
                    if s.get("url"):
                        st.caption(s["url"])
                    st.text(s["content"][:300] + ("..." if len(s["content"]) > 300 else ""))
        if "quality_reason" in msg and msg.get("quality_reason"):
            st.caption(f"质量检查：{msg['quality_reason']}")

        # Feedback buttons
        if msg["role"] == "assistant" and msg.get("sources"):
            feedback = msg.get("_feedback")
            fb_key = f"fb_{msg_idx}"
            col1, col2, col3 = st.columns([1, 1, 4])
            if feedback is None:
                with col1:
                    if st.button("👍 有用", key=f"{fb_key}_up"):
                        st.session_state.messages[msg_idx]["_feedback"] = "helpful"
                        if msg.get("_db_id"):
                            update_feedback(msg["_db_id"], "helpful")
                        st.rerun()
                with col2:
                    if st.button("👎 无用", key=f"{fb_key}_down"):
                        st.session_state.messages[msg_idx]["_feedback"] = "unhelpful"
                        if msg.get("_db_id"):
                            update_feedback(msg["_db_id"], "unhelpful")
                        st.rerun()
            else:
                feedback_label = {"helpful": "✅ 有用", "unhelpful": "❌ 无用"}.get(feedback, feedback)
                st.caption(f"反馈：{feedback_label}")

# 输入框
if prompt := st.chat_input("请输入你的问题..."):
    # 显示用户消息
    st.chat_message("user").markdown(prompt)

    # 保存对话
    if not st.session_state.current_conv_id:
        conv = create_conversation()
        st.session_state.current_conv_id = conv["id"]
        st.session_state.thread_id = conv["thread_id"]

    # 自动命名（第一条消息）
    conv_id = st.session_state.current_conv_id
    conv = get_conversation(conv_id)
    if conv and conv["title"] == "新对话":
        new_title = prompt[:30] + ("..." if len(prompt) > 30 else "")
        update_title(conv_id, new_title)

    add_message(conv_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 检查知识库
    if not st.session_state.kb_ready:
        with st.chat_message("assistant"):
            st.error(f"知识库加载失败：{st.session_state.kb_error}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"知识库加载失败：{st.session_state.kb_error}",
        })
        st.rerun()

    if st.session_state.doc_count == 0:
        from config.settings import TAVILY_API_KEY
        from config.settings import _is_configured_api_key

        if not _is_configured_api_key(TAVILY_API_KEY):
            with st.chat_message("assistant"):
                st.error("知识库为空！请先上传文档或确认预设文档已加载。")
            st.session_state.messages.append({
                "role": "assistant",
                "content": "知识库为空，请先通过侧边栏上传文档。",
            })
            st.rerun()

    # 流式调用 LangGraph
    with st.chat_message("assistant"):
        t0 = time.monotonic()
        answer_placeholder = st.empty()
        progress_placeholder = st.empty()
        source_expander = None
        quality_caption = None

        node_labels = {
            "route_question": "问题路由",
            "rewrite_query": "查询改写",
            "retrieve_docs": "混合检索",
            "rerank_docs": "结构化重排",
            "generate_answer": "生成回答",
            "check_quality": "质量检查",
            "web_search": "联网搜索",
            "answer_from_history": "会话记忆",
            "summarize_history": "会话总结",
            "handle_missing_context": "证据不足兜底",
            "handle_clarification": "模糊问题提示",
        }

        try:
            events = run_query(
                question=prompt,
                thread_id=st.session_state.thread_id,
                knowledge_base=st.session_state.kb,
                stream_tokens=True,
                web_search_enabled=st.session_state.web_search_enabled,
            )

            accumulated_answer = ""
            seen_nodes = set()
            final_sources = []
            final_quality = ""

            for mode, data in events:
                if mode == "updates":
                    for node_name, update in data.items():
                        node_label = node_labels.get(node_name, node_name)
                        if node_label not in seen_nodes:
                            seen_nodes.add(node_label)
                        progress_placeholder.caption(
                            f"正在执行：{' → '.join(seen_nodes)}"
                        )
                        if isinstance(update, dict):
                            accumulated_answer = update.get("answer", accumulated_answer)
                            if update.get("sources"):
                                final_sources = update["sources"]
                            if update.get("quality_reason"):
                                final_quality = update["quality_reason"]

                elif mode == "messages":
                    chunk, metadata = data
                    if (
                        isinstance(chunk, AIMessageChunk)
                        and chunk.content
                        and metadata.get("langgraph_node") == "generate_answer"
                    ):
                        answer_placeholder.markdown(accumulated_answer + chunk.content + "▌")
                        accumulated_answer += chunk.content

            progress_placeholder.empty()

            answer = accumulated_answer.strip() or "抱歉，我无法回答这个问题。"
            answer_placeholder.markdown(answer)

            if final_sources:
                with st.expander("📎 引用来源"):
                    for s in final_sources:
                        score_text = f" · score={s.get('score', 0):.4f}" if s.get("score") is not None else ""
                        loc_parts = []
                        if s.get("chunk_index"):
                            loc_parts.append(f"分段 #{s['chunk_index']}")
                        if s.get("page"):
                            loc_parts.append(f"第 {s['page']} 页")
                        loc_text = f"（{', '.join(loc_parts)}）" if loc_parts else ""
                        st.caption(f"**{s['source']}**{loc_text}{score_text}")
                        if s.get("url"):
                            st.caption(s["url"])
                        st.text(s["content"][:300] + ("..." if len(s["content"]) > 300 else ""))
            if final_quality:
                st.caption(f"质量检查：{final_quality}")

            # Save to session
            msg_entry = {
                "role": "assistant",
                "content": answer,
                "sources": final_sources,
                "quality_reason": final_quality,
            }
            st.session_state.messages.append(msg_entry)

            # Save to DB
            add_message(
                conv_id,
                "assistant",
                answer,
                sources=final_sources,
                quality_reason=final_quality,
            )

            # Metrics
            elapsed = time.monotonic() - t0
            try:
                log_query(
                    question=prompt,
                    thread_id=st.session_state.thread_id,
                    question_type="knowledge_base",
                    retrieval_count=len(final_sources),
                    retry_count=0,
                    quality_ok=not bool(final_quality),
                    quality_reason=final_quality,
                    source_count=len(final_sources),
                    elapsed_ms=int(elapsed * 1000),
                    answer=answer,
                )
            except Exception:
                pass

        except Exception as e:
            error_msg = f"出错了: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg,
            })
