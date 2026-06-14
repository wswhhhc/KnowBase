# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 运行 Streamlit 应用
uv run streamlit run src/app.py

# 运行所有测试
uv run python -m unittest discover -s tests

# 运行单个测试文件
uv run python -m unittest tests.test_graph
uv run python -m unittest tests.test_knowledge_base
uv run python -m unittest tests.test_loaders
uv run python -m unittest tests.test_routing
uv run python -m unittest tests.test_utils
uv run python -m unittest tests.test_settings

# 运行单个测试方法
uv run python -m unittest tests.test_graph.GraphRoutingTests.test_run_query_uses_thread_memory_for_followup

# 包同步（安装依赖）
uv sync

# 离线 RAG 评估
uv run python -m src.evaluate
```

## Architecture

**KnowBase** — LangChain + LangGraph 知识库问答助手，Streamlit UI + Chroma 本地向量库 + BM25 混合检索。

### 核心模块

| 模块 | 职责 |
|------|------|
| **`src/app.py`** | Streamlit 入口。初始化知识库，管理对话/消息，调用 LangGraph 工作流并显示流式输出。会话持久化到 SQLite。 |
| **`src/graph.py`** | LangGraph 工作流定义。节点：问题路由 → 查询改写 → 混合检索 → 重排序 → 生成回答 → 质量检查 →（联网搜索兜底/扩检重试）。`SqliteSaver` 保存线程状态。 |
| **`src/knowledge_base.py`** | 知识库核心。Chroma 向量库存储/检索，jieba BM25 索引，RRF 融合排序。`chunk_id` 基于 `source:chunk_index:content_hash[:16]` 稳定生成，基于 hash 去重。 |
| **`src/loaders.py`** | 多格式文档加载器。支持 `.txt` / `.md` / `.pdf` / `.docx` / `.html(.htm)`。新增 `load_url()` 支持从 URL 抓取网页内容。 |
| **`src/conversations.py`** | 对话管理。SQLite 存储对话元数据和消息记录，支持 CRUD 和 Markdown 导出。 |
| **`src/kb_browser.py`** | 知识库内容浏览子页面。按来源筛选、关键词搜索、查看文档片段内容。 |
| **`src/web_search.py`** | 联网搜索模块。基于 Tavily API（可选），由用户在侧边栏开关控制。 |
| **`src/utils.py`** | 文件上传校验（扩展名白名单和大小限制）和临时保存。 |
| **`src/metrics.py`** | RAG 查询本地 JSONL 日志，记录每次查询的耗时、检索数量、质量决策。 |
| **`src/evaluate.py`** | 离线评估脚本，读取 `docs/rag_eval_dataset.jsonl`，输出 groundedness/correctness 等指标。 |
| **`src/metrics_dashboard.py`** | 指标面板，展示耗时分布、每日趋势、质量通过率、最近查询。 |
| **`config/settings.py`** | pydantic-settings 驱动，从 `.env` 读取配置。`CHROMA_API_KEY` 会回退作为 `SILICONFLOW_API_KEY`。 |

### LangGraph 工作流数据流

```
上传/预设文档 → TextLoader → RecursiveCharacterTextSplitter → Chroma 入库 + BM25 重建
用户提问 → route_question(LLM分类+正则兜底)
  → rewrite_query(LLM改写) → retrieve_docs(向量召回N=30→候选集BM25→RRF融合)
  → rerank_docs(条件式LLM精排，分数差距大/短问题/策略fast时跳过) → generate_answer(带邻居chunk+标题链)
  → check_quality(规则层→LLM审核→不合格→web_search→扩检索重试→重新生成)
```

路由分支（`route_after_classifier`）：`knowledge_base` → 检索问答；`chat_memory` → 回答历史；`conversation_summary` → 总结；`clarification` → 模糊提示。

流式输出：`run_query(stream_tokens=True)` 通过 `stream_mode=["updates", "messages"]` 同时输出节点进度和 LLM token。

### 对话状态管理

- **LangGraph** 通过 `SqliteSaver` 持久化每个 `thread_id` 的线程状态（checkpoint），支持对话记忆。
- **Streamlit** 管理 UI 层的消息列表 `st.session_state.messages`。
- **对话模块**（`conversations.py`）将用户/助手消息持久化到 `data/conversations.db`，支持新建/切换/删除/导出。
- 重命名：首次消息自动截取前 30 字作为对话标题。

### 检索增强细节

- `hybrid_search`：向量召回 N=30 条候选（`VECTOR_CANDIDATE_K`），在候选集上构建临时 BM25 索引并打分，RRF 融合取 TopK。不再对全库做 BM25。
- 邻居 chunk 补全：检索结果自动带上同一来源中前后各 1 个 chunk，减少断章取义。
- 标题追踪：切片时检测 `#`/`##` 标题，记录到 chunk metadata 的 `section` 字段，展示在来源上下文中。
- `rerank_docs`：条件式 LLM 精排。候选间 RRF 分数差大、问题短（<50 字）、策略为 `fast` 时跳过。
- `score_threshold`：RRF 分数阈值过滤。
- 分层质量检查：规则层（空召回/回答过短/已联网）→ LLM 审核 → Tavily 联网 → 扩检索重试，最多 `MAX_RETRIES` 次。
- 搜索策略：`fast`（无 rerank）、`balanced`（默认、条件 rerank）、`high_quality`（必走 rerank）。
- 切片：`RecursiveCharacterTextSplitter` 按标题/段落/句末分割，chunk_size=800, overlap=50。支持 `source_type` 过滤。

### 关键约定

- 包管理用 `uv`，不用 pip。
- API Key 在 `.env` 中配置，`require_siliconflow_api_key()` 检查并抛出可读错误。
- LLM 和 embedding 都通过硅基流动 OpenAI-compatible API 调用。
- Chroma 持久化在 `data/chroma_db/`，`clear()` 会删除 collection 并重建。
- `all_docs` 在内存中维护 BM25 索引，重启时从 Chroma 恢复（`_load_existing_documents`）。
- 联网搜索 Tavily 为可选依赖，未配 Key 时不显示在 UI 中。
- `.env` 中的 `CHROMA_API_KEY` 会回退作为 `SILICONFLOW_API_KEY`。

### 测试策略

- 单元测试用 `unittest`，mock LLM 调用（`FakeLLM` / `FakeResponse`）。
- `test_graph.py` — mock LLM 测试路由分支、web_search 兜底、重试逻辑和线程记忆。
- 其他测试文件各自覆盖对应模块的纯函数逻辑。
