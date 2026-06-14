# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 运行 FastAPI 后端
cd backend && uv run uvicorn src.api.main:app --reload --port 8000

# 运行 React 前端
cd frontend && npm run dev

# 运行所有测试（从 backend 目录）
cd backend && uv run python -m unittest discover -s tests

# 运行单个测试文件
cd backend && uv run python -m unittest tests.test_graph
cd backend && uv run python -m unittest tests.test_knowledge_base

# 包同步（安装依赖）
cd backend && uv sync
cd frontend && npm install

# 离线 RAG 评估
cd backend && uv run python -m src.evaluate
```

## Architecture

**KnowBase** — LangChain + LangGraph 知识库问答助手。

### 项目结构

```
KnowBase/
├── backend/              # FastAPI 后端（前后端分离架构）
│   ├── config/           # pydantic-settings 配置
│   ├── src/
│   │   ├── api/          # FastAPI 路由层
│   │   │   ├── main.py           # 应用入口 + CORS
│   │   │   ├── deps.py           # KnowledgeBase 依赖注入
│   │   │   ├── models.py         # Pydantic 请求/响应模型
│   │   │   └── routes/
│   │   │       ├── chat.py           # SSE 流式聊天
│   │   │       ├── conversations.py  # 对话 CRUD
│   │   │       ├── documents.py      # 上传/URL导入/来源管理
│   │   │       ├── knowledge_base.py # 知识库浏览
│   │   │       └── metrics.py        # 查询日志
│   │   ├── graph.py          # LangGraph 工作流
│   │   ├── knowledge_base.py # Chroma + BM25 核心
│   │   ├── conversations.py  # 对话管理模块
│   │   ├── loaders.py        # 文档加载器
│   │   ├── web_search.py     # Tavily 搜索
│   │   ├── metrics.py        # JSONL 日志
│   │   └── utils.py          # 工具函数
│   └── tests/
├── frontend/             # React + Vite + Tailwind 前端
│   └── src/
│       ├── components/
│       │   ├── ui/       # shadcn/ui 组件
│       │   ├── ChatArea.tsx
│       │   └── Sidebar.tsx
│       ├── hooks/
│       │   ├── useChat.ts    # SSE 流式聊天 hook
│       │   └── useData.ts    # 对话/文档管理 hook
│       └── lib/
│           ├── api.ts        # API 客户端
│           └── utils.ts      # 工具函数
├── config/               # 共享配置（pydantic-settings）
└── data/                 # 共享数据（chroma/checkpoints/logs）
```

### 核心模块

| 模块 | 职责 |
|------|------|
| **`backend/src/api/`** | FastAPI REST API，SSE 流式聊天，CORS 代理到前端 |
| **`backend/src/graph.py`** | LangGraph 工作流定义。节点：问题路由 → 查询改写 → 混合检索 → 重排序 → 生成回答 → 质量检查 →（联网搜索兜底/扩检重试）。`SqliteSaver` 保存线程状态。 |
| **`backend/src/knowledge_base.py`** | 知识库核心。Chroma 向量库存储/检索，jieba BM25 索引，RRF 融合排序。`chunk_id` 基于 `source:chunk_index:content_hash[:16]` 稳定生成，基于 hash 去重。 |
| **`backend/src/loaders.py`** | 多格式文档加载器。支持 `.txt` / `.md` / `.pdf` / `.docx` / `.html(.htm)`。新增 `load_url()` 支持从 URL 抓取网页内容。 |
| **`backend/src/conversations.py`** | 对话管理。SQLite 存储对话元数据和消息记录，支持 CRUD 和 Markdown 导出。 |
| **`backend/src/web_search.py`** | 联网搜索模块。基于 Tavily API（可选）。 |
| **`backend/src/utils.py`** | 文件上传校验（扩展名白名单和大小限制）和临时保存。 |
| **`backend/src/metrics.py`** | RAG 查询本地 JSONL 日志，记录每次查询的耗时、检索数量、质量决策。 |
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
