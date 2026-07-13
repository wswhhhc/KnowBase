# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 后端
cd backend && uv run uvicorn src.api.main:app --reload --port 8000

# 前端
cd frontend && npm run dev

# 一键启动（支持 bash / PowerShell）
bash scripts/dev.sh
scripts\dev.bat

# Docker
docker compose up --build

# ---- 测试 ----

# 后端全部测试
cd backend && uv run pytest tests --tb=short -q

# 后端单个测试文件
cd backend && uv run pytest tests/test_graph.py -q

# 前端全部测试
cd frontend && npm test

# 前端单文件测试
cd frontend && npx vitest src/test/__tests__/components/ChatArea.test.tsx

# 前端测试 watch 模式
cd frontend && npm run test:watch

# ---- 质量门禁 ----
bash scripts/run-checks.sh
# 内部依次执行：后端 pytest → check-structure.py → 前端 vitest → 前端构建 → API 类型漂移检查

# ---- 包同步 ----
cd backend && uv sync
cd frontend && npm install

# ---- 数据库 ----
cd backend && uv run alembic upgrade head
cd backend && uv run alembic downgrade -1

# ---- 契约同步（后端 schema 变更后） ----
cd backend && uv run python scripts/export_openapi.py
cd frontend && npm run gen-api-types
# CI 会阻止契约/类型未同步的提交：npm run check-api-types

# ---- 离线 RAG 评估 ----
cd backend && uv run python -m src.evaluate
```

## Architecture

**KnowBase** — LangChain + LangGraph 知识库问答助手。React 19 前端 + FastAPI 后端前后端分离。

### 数据流

```
用户提问 → problem routing (LLM+正则)
  → 查询改写 (LRU 缓存，命中跳过)
  → 混合检索 (Chroma 向量 + BM25 → RRF 融合)
  → 条件式 LLM 精排 (分数差距大/短问题/策略 fast 时跳过)
  → 生成回答 (邻居 chunk + 标题链)
  → 质量检查 (规则层→LLM→不合格→web_search/扩检索重试，最多 MAX_RETRIES 次)
  → SSE 流式返回 (ChatStreamService → chat_debug + chat_persistence)
```

### 后端分层

```
api/        HTTP 协议、鉴权、参数校验、响应映射   → 不包含核心逻辑
services/   跨 rag/jobs/persistence 的应用用例编排 → 不依赖 FastAPI/api.models
graph/      LangGraph 工作流节点                  → 不反向依赖 api.models
rag/        知识库导入/检索/向量存储               → 不反向依赖 api.models
persistence/ Postgres/SQLite repository 细节       → 路由与服务直接依赖
config/     pydantic-settings + 运行时覆写
```

`graph/nodes.py` 已拆分为独立节点模块：`history_nodes`、`generation_nodes`、`finalization_nodes`、`retrieval_nodes`、`quality_nodes`、`web_search_nodes`。禁止继续将 `src.graph.nodes` 当主入口使用。

结构守卫脚本 `scripts/check-structure.py` 会在 CI 中校验禁止的导入和文件结构回退。

### 关键约定

- **包管理**: `uv`（非 pip），`.env` 放 `backend/.env`，启动用 `uv run`
- **容器化**: `docker compose up --build`，Dockerfile 在 `docker/`
- **持久化**: Chroma → `runtime/local/chroma_db/`，对话 → `runtime/local/conversations.db`（Alembic），checkpoints → `runtime/local/checkpoints.db`
- **配置**: `backend/src/config/settings.py`（pydantic-settings），`CHROMA_API_KEY` 回退为 `SILICONFLOW_API_KEY`
- **鉴权**: `deps.py:verify_api_key`，`API_KEY` 为空时本地开发跳过
- **搜索策略**: `fast`(无 rerank)、`balanced`(条件 rerank)、`high_quality`(必 rerank)、`deep`(扩检索)；偏好由 `features/chat/hooks/useSearchPreferences.ts` 持久化，移动端收进复用弹层
- **SSE 流**: `backend/src/api/chat_stream_service.py`（ChatStreamService），`chat.py` 路由只负责 HTTP 适配。调试逻辑拆至 `chat_debug.py`，持久化拆至 `chat_persistence.py`
- **文档导入**: `backend/src/services/` 负责导入、同步操作、维护任务和审计编排；`api/document_job_stream.py` 负责任务进度 SSE，`routes/documents.py` 只保留 HTTP 映射
- **Pin/Exclude**: 独立 `pinned_sources` 表，非 debug_info JSON blob，通过 `/pin-state` 查询
- **前端 API 客户端**: `frontend/src/shared/api/` 下（非旧 `lib/api.ts`），含 SSEParser 和 createChatStreamAdapter
- **前端字号**: `text-2xs`(10px) / `text-xs`(12px) / `text-sm`(14px)，禁用 `text-[Xpx]`
- **图标**: 全项目 lucide-react，禁用 emoji 作为 UI 图标

### 契约与类型同步

`backend/openapi.json` 是提交态 API 快照，`frontend/src/shared/api/api-types.openapi.ts` 是前端生成物。当 FastAPI 路由或 Pydantic schema 改动时：
1. 导出 `backend/openapi.json`
2. 重新生成前端类型 `npm run gen-api-types`
3. CI 通过 `npm run check-api-types` 校验同步

手写 SSE 类型在 `frontend/src/shared/api/api-types.ts`，由后端测试校验与 Pydantic 模型同步。

### 测试策略

| 层 | 框架与命令 | 策略 |
|---|---|---|
| 后端 | pytest：`cd backend && uv run pytest tests --tb=short -q` | LLM mock(FakeLLM)，Chroma patch，临时数据库隔离；覆盖 SSE、任务、路由、结构与类型契约 |
| 前端 | Vitest + Testing Library：`cd frontend && npm test` | ReadableStream 模拟 SSE（含 CRLF），mock 数据在 `src/test/mocks/data.ts`；覆盖 hooks、组件、API 与类型漂移 |

### 关键模块

**后端**:

| 文件 | 职责 |
|---|---|
| `api/chat_stream_service.py` | SSE 流编排（调试/持久化拆至独立模块） |
| `api/chat_debug.py` | DebugState dataclass + 节点调试信息累加 |
| `api/chat_persistence.py` | 对话持久化 + debug payload 序列化 |
| `api/routes/` | 路由层：HTTP 协议、鉴权、参数校验与响应映射 |
| `services/` | 文档导入等跨 `rag/jobs/persistence` 的应用用例编排，不依赖 FastAPI 协议对象 |
| `graph/graph.py` | LangGraph 图定义 |
| `graph/history_nodes.py` | 历史记录与重写节点 |
| `graph/generation_nodes.py` | 回答生成节点 |
| `graph/finalization_nodes.py` | 最终格式化节点 |
| `graph/retrieval_nodes.py` | 检索节点 |
| `graph/quality_nodes.py` | 质量检查节点 |
| `graph/web_search_nodes.py` | 联网搜索节点 |
| `graph/routing.py` | 条件路由函数 |
| `graph/state.py` | GraphState TypedDict + Pydantic 决策模型 |
| `graph/utils.py` | 图工作流通用工具（LLM/上下文格式化/解析） |
| `rag/knowledge_base.py` | 门面类（IngestionService + Retriever + HotspotTracker） |
| `rag/models.py` | 检索结果数据类 + 来源归一化 |
| `rag/loaders.py` | 多格式文档加载器（含 SSRF 防护 IP 检测） |
| `rag/web_search.py` | Tavily 联网搜索 |
| `persistence/` | Postgres/SQLite repository（conversation/bookmark/message/pin/workspace） |
| `config/settings.py` | pydantic-settings 配置 |

**前端**:

| 文件 | 职责 |
|---|---|
| `components/browser/` | BrowserPage 拆分：7 个子组件（BrowserHeader/DocumentActions/SearchToolbar/DebugSandbox/GridView/SliceView/ChunkDetailDialog） |
| `components/sidebar/` | ConversationList/DocumentPanel/KBSummary/DashboardSummary；`document-panel/` 下拆分导入 Controls、Feedback 与来源列表 |
| `pages/chat/ChatPage.tsx` | 对话页面装配：导航、搜索偏好接线、消息列表和输入编辑器 |
| `components/chat/` | Chat 展示区块：搜索偏好控件、消息列表、输入编辑器 |
| `features/chat/hooks/` | Chat 偏好持久化与输入编辑器状态 |
| `features/dashboard/` | Dashboard 日志请求与纯指标模型 |
| `components/MessageBubble.tsx` | 消息气泡（引用编号、证据标签、收藏/反馈/复制/导出、顶部操作主次分层 + 更多菜单） |
| `components/EmptyState.tsx` | 三种空状态模式（onboarding/first-question/returning），根据工作区文档数和对话数动态渲染 |
| `components/ErrorBoundary.tsx` | 组件级错误边界（支持 fallback prop） |
| `hooks/useChat.ts` | SSE 流式聊天 hook（逻辑委托至 chat/ 子模块） |
| `hooks/chat/` | 聊天状态拆分：`types.ts` 类型定义、`useChatMessages.ts` 消息列表管理、`usePinnedSourcesState.ts` 来源固定/排除状态 |
| `shared/api/` | 分模块 API 客户端；`client.ts` 负责请求基座，`sse.ts` 负责 SSEParser 与流适配，各领域模块由 `index.ts` 汇总导出 |
| `shared/api/api-types.ts` | 手写 SSE 类型 |
| `shared/api/api-types.openapi.ts` | 从 OpenAPI 生成的前端类型 |
| `app/` | 应用壳、导航、入口装配 |
| `pages/` | 页面级容器 |
| `features/` | 功能状态与交互逻辑 |

### 工作区语义

工作区是应用层的作用域组织方式，**不是**安全边界或多租户隔离方案。删除工作区时对话和书签会回落到默认工作区。
