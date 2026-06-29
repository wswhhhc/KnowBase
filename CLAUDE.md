# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 运行 FastAPI 后端
cd backend && uv run uvicorn src.api.main:app --reload --port 8000

# 运行 React 前端
cd frontend && npm run dev

# 运行所有后端测试
cd backend && uv run python -m unittest discover -v

# 运行单个后端测试文件
cd backend && uv run python -m unittest tests.test_graph -v

# 运行所有前端测试
cd frontend && npm test

# 前端测试（监听/覆盖率）
cd frontend && npm run test:watch
cd frontend && npm run test:coverage

# 包同步
cd backend && uv sync
cd frontend && npm install

# Alembic 迁移（自动在 init_db 时执行，也可手动控制）
cd backend && uv run alembic upgrade head
cd backend && uv run alembic downgrade -1

# 离线 RAG 评估
cd backend && uv run python -m src.evaluate
```

## Architecture

**KnowBase** — LangChain + LangGraph 知识库问答助手。React 前端 + FastAPI 后端前后端分离架构。

### 项目结构

```
KnowBase/
├── backend/                    # FastAPI 后端
│   ├── migrations/             # Alembic 数据库迁移
│   ├── config/
│   │   └── settings.py         # pydantic-settings，含环境变量 → .env 映射
│   ├── src/
│   │   ├── api/                # FastAPI 路由层
│   │   │   ├── chat_stream_service.py  # SSE 流编排（ChatStreamService，替代原 event_generator 闭包）
│   │   │   ├── main.py / deps.py / models.py
│   │   │   └── routes/*
│   │   ├── graph.py            # LangGraph 图定义
│   │   ├── graph_nodes.py      # 工作流节点函数
│   │   ├── graph_routing.py    # 条件路由函数
│   │   ├── graph_utils.py      # 工作流工具函数
│   │   ├── graph_state.py      # GraphState TypedDict + Pydantic 决策模型
│   │   ├── knowledge_base.py   # 门面类（IngestionService / Retriever / HotspotTracker）
│   │   ├── kb_models.py        # 检索结果数据类
│   │   ├── conversations.py    # 对话 CRUD + 工作区 + 书签 + pin 状态（SQLite + Alembic）
│   │   ├── loaders.py          # 多格式文档加载器（txt/md/pdf/docx/html + URL）
│   │   ├── web_search.py       # Tavily 联网搜索（可选）
│   │   ├── metrics.py          # 查询 JSONL 日志
│   │   ├── chat_utils.py       # 节点标签/指标记录/标题生成
│   │   └── utils.py            # 文件上传校验 + 唯一临时文件名
│   └── tests/                  # 30+ 文件，441 用例
├── frontend/                   # React 19 + Vite + Tailwind
│   └── src/
│       ├── components/
│       │   ├── browser/        # BrowserPage 拆分：7 个子组件
│       │   ├── sidebar/        # ConversationList / DocumentPanel / KBSummary / DashboardSummary
│       │   ├── ui/             # shadcn/ui（含 SkeletonCard/SkeletonGrid）
│       │   ├── ChatArea.tsx    # 对话界面（搜索策略可见 + localStorage 持久化）
│       │   ├── Sidebar.tsx     # 侧栏导航 + 视图切换 + 主题切换
│       │   ├── BrowserPage.tsx # 知识库浏览（薄编排层，原 913 行 → ~270 行）
│       │   ├── DashboardPage.tsx / EmptyState.tsx / MessageBubble.tsx / DebugPanel.tsx
│       │   └── ErrorBoundary.tsx  # 组件级错误边界（支持 fallback prop）
│       ├── hooks/              # useChat（SSE 流式）/ useData / useTheme
│       └── lib/                # api.ts（SSEParser + 全量 API 客户端）/ api-types.ts / utils.ts
│   ├── data/                   # chroma_db / checkpoints.db / conversations.db / logs
├── docs/
│   └── tests/                  # 12 份测试文档
└── scripts/                    # 一键启动脚本
```

### API 端点

| 端点 | 功能 |
|------|------|
| `POST /api/chat/stream` | SSE 流式聊天（事件：node/token/sources/debug/done） |
| `GET/POST/DELETE /api/conversations` | 对话 CRUD |
| `PATCH /api/conversations/:id` | 重命名 |
| `GET /api/conversations/:id/messages` | 消息列表 |
| `GET /api/conversations/:id/pin-state` | Pin/exclude 状态 |
| `POST /api/conversations/:id/messages/:msg_id/feedback` | 消息反馈 |
| `GET /api/conversations/:id/export` | Markdown/JSON 导出 |
| `POST /api/documents/upload` | 文件上传（流式读取） |
| `POST /api/documents/ingest-url` | URL 导入 |
| `DELETE /api/documents/source/:name` | 删除来源 |
| `POST /api/documents/clear` | 清空知识库 |
| `GET /api/knowledge-base/stats` | 统计 |
| `GET /api/knowledge-base/chunks` | 分页浏览 |
| `GET /api/knowledge-base/chunks/{chunk_id}` | 单 chunk 直查 |
| `GET /api/knowledge-base/sources` | 来源列表 |
| `GET /api/knowledge-base/config` | KB 配置 |
| `GET /api/knowledge-base/hotspots` | 热点追踪 |
| `GET /api/metrics/logs` | 查询日志 |
| `DELETE /api/metrics/logs/today` | 删除今日日志 |
| `GET/POST/PATCH/DELETE /api/workspaces` | 工作区 CRUD |
| `GET/POST/DELETE /api/bookmarks` | 书签 CRUD |
| `GET /api/health` | 健康检查 |

### LangGraph 工作流

```
上传/预设文档 → TextLoader → RecursiveCharacterTextSplitter → Chroma 入库 + BM25 重建
用户提问 → route_question(LLM分类+正则兜底)
  → rewrite_query(LLM改写) → retrieve_docs(向量召回 → 候选集BM25 → RRF融合)
  → rerank_docs(条件式LLM精排，分数差距大/短问题/策略fast时跳过)
  → generate_answer(带邻居chunk+标题链)
  → check_quality(规则层→LLM审核→不合格→web_search→扩检索重试，最多 MAX_RETRIES 次)
```

### 关键约定

- 包管理用 `uv`，不用 pip。`.env` 放在 `backend/.env`。启动靠 `uv run`，无需手动 `sys.path.insert`。
- `backend/config/settings.py` 是唯一配置入口，pydantic-settings 驱动。`CHROMA_API_KEY` 回退作为 `SILICONFLOW_API_KEY`。
- LLM 和 embedding 都通过硅基流动 OpenAI-compatible API 调用。
- Chroma 持久化在 `data/chroma_db/`；对话在 `data/conversations.db`（Alembic 迁移管理）；checkpoints 在 `data/checkpoints.db`。
- API Key 鉴权：`deps.py` 提供 `verify_api_key` 依赖，`API_KEY` 空值时跳过（本地开发无感）。`load_preset_documents` 在 `lifespan` 中执行。
- Tavily 为可选依赖，未配 Key 时不显示在 UI 中。
- 搜索策略：`fast`（无 rerank）、`balanced`（默认、条件 rerank）、`high_quality`（必走 rerank）、`deep`（扩检索）。偏好通过 `localStorage` 持久化。
- 前端 `api.ts` 包含 `SSEParser`（支持 CRLF/CR）和 `createChatStreamAdapter`，自动带 Authorization 头，后端所有写操作 + 读操作端点均受鉴权保护。
- SSE 流式编排已在 3.1 重构中提取为 `ChatStreamService`（`backend/src/api/chat_stream_service.py`），`chat.py` 路由仅 27 行。
- Pin/exclude 状态从 `debug_info` JSON blob 迁至独立 `pinned_sources` 表（`conversations.py`），通过 `/pin-state` 端点查询。
- BrowserPage 已从 913 行单体拆为 7 个子组件（`components/browser/`）：BrowserHeader、DocumentActions、SearchToolbar、DebugSandbox、GridView、SliceView、ChunkDetailDialog。
- 前端字号系统使用 `text-2xs`（10px）、`text-xs`（12px）、`text-sm`（14px）标准 token，禁用任意宽高值（`text-[Xpx]`）。
- 所有 lucide 图标统一下，禁用 emoji 作为 UI 图标（MessageBubble.tsx 已全部替换）。

### 测试策略

**后端**：Python unittest（30+ 文件，441 用例）。LLM mock 用 `FakeLLM`/`FakeResponse` + `unittest.mock.patch`，Chroma mock 用 patch 替换，SQLite 用 `tempfile.TemporaryDirectory` 隔离。含 SSE 手写类型漂移检测（`test_sse_type_sync`）、ChatRoute SSE 集成测试（7 种事件类型）、ChatStreamService 单元测试、AST 签名校验（`test_chat_metrics_signature`）、工作区/书签/路由分类/版本模式/pin-exclude 测试。

**前端**：vitest + @testing-library/react（22 文件，195 用例）。SSE 用 `ReadableStream` 模拟（含 CRLF 回归测试），mock 数据在 `src/test/mocks/data.ts`。覆盖 hooks、组件渲染、交互、API 客户端、类型漂移检测（`type-drift-check.test.ts`）。含 Sidebar 交互测试（上传/URL 导入 toast 反馈）、ChatArea 策略按钮可见性、BrowserPage 拆分后交互测试、DebugPanel 覆盖率。

```bash
# 后端全部
cd backend && uv run python -m unittest discover -v

# 前端全部
cd frontend && npm test
```
