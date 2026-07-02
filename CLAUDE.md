# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 后端
cd backend && uv run uvicorn src.api.main:app --reload --port 8000

# 前端
cd frontend && npm run dev

# 后端全部测试
cd backend && uv run python -m unittest discover -v

# 后端单个测试文件
cd backend && uv run python -m unittest tests.test_graph -v

# 前端全部测试
cd frontend && npm test

# 前端单文件测试
cd frontend && npx vitest src/test/__tests__/components/ChatArea.test.tsx

# 包同步
cd backend && uv sync
cd frontend && npm install

# Alembic（init_db 时自动执行，也可手动）
cd backend && uv run alembic upgrade head
cd backend && uv run alembic downgrade -1

# 离线 RAG 评估
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

### 关键约定

- **包管理**: `uv`（非 pip），`.env` 放 `backend/.env`，启动用 `uv run`
- **容器化**: `docker compose up --build`，Dockerfile 在 `docker/`
- **持久化**: Chroma → `data/chroma_db/`，对话 → `data/conversations.db`（Alembic），checkpoints → `data/checkpoints.db`
- **配置**: `backend/src/config/settings.py`（pydantic-settings），`CHROMA_API_KEY` 回退为 `SILICONFLOW_API_KEY`
- **鉴权**: `deps.py:verify_api_key`，`API_KEY` 为空时本地开发跳过
- **搜索策略**: `fast`(无 rerank)、`balanced`(条件 rerank)、`high_quality`(必 rerank)、`deep`(扩检索)，偏好存 `localStorage`。移动端收进弹层
- **SSE 流**: `backend/src/api/chat_stream_service.py`（ChatStreamService），`chat.py` 路由仅 27 行。调试逻辑拆至 `chat_debug.py`，持久化拆至 `chat_persistence.py`
- **Pin/Exclude**: 独立 `pinned_sources` 表，非 debug_info JSON blob，通过 `/pin-state` 查询
- **前端字号**: `text-2xs`(10px) / `text-xs`(12px) / `text-sm`(14px)，禁用 `text-[Xpx]`
- **图标**: 全项目 lucide-react，禁用 emoji 作为 UI 图标

### 测试策略

| 层 | 框架 | 文件 | 用例 | 策略 |
|---|---|---|---|---|
| 后端 | unittest | 28 | 444 | LLM mock(FakeLLM)，Chroma patch，SQLite tempdir 隔离。SSE 类型漂移检测、AST 签名校验 |
| 前端 | vitest + @testing-library/react | 23 | 206 | ReadableStream 模拟 SSE (含 CRLF)，mock 数据在 `src/test/mocks/data.ts`。hooks/组件/API/类型漂移全覆盖 |

### 关键模块

**后端**:

| 文件 | 职责 |
|---|---|
| `api/chat_stream_service.py` | SSE 流编排（~190 行，调试/持久化拆至独立模块） |
| `api/chat_debug.py` | DebugState dataclass + 节点调试信息累加 |
| `api/chat_persistence.py` | 对话持久化 + debug payload 序列化 |
| `api/routes/` | 路由层（7 个路由文件，平均 <50 行） |
| `graph/graph.py` | LangGraph 图定义 |
| `graph/nodes.py` | 工作流节点函数（rewrite/retrieve/rerank/generate/check） |
| `graph/routing.py` | 条件路由函数 |
| `graph/state.py` | GraphState TypedDict + Pydantic 决策模型 |
| `graph/utils.py` | 图工作流通用工具（LLM/上下文格式化/解析） |
| `rag/knowledge_base.py` | 门面类（IngestionService + Retriever + HotspotTracker） |
| `rag/models.py` | 检索结果数据类 + 来源归一化 |
| `rag/loaders.py` | 多格式文档加载器（含 SSRF 防护 IP 检测） |
| `rag/web_search.py` | Tavily 联网搜索 |
| `conversations.py` | 对话/工作区/书签/pin CRUD（SQLite + Alembic） |
| `metrics.py` | 查询 JSONL 日志 |
| `config/settings.py` | pydantic-settings 配置 |

**前端**:

| 文件 | 职责 |
|---|---|
| `components/browser/` | BrowserPage 拆分：7 个子组件（BrowserHeader/DocumentActions/SearchToolbar/DebugSandbox/GridView/SliceView/ChunkDetailDialog） |
| `components/sidebar/` | ConversationList/DocumentPanel/KBSummary/DashboardSummary |
| `components/ChatArea.tsx` | 对话页（动态 EmptyState 按工作区分 onboarding/first-question/returning 三种场景；移动端检索策略弹层；搜索策略 radiogroup + localStorage） |
| `components/MessageBubble.tsx` | 消息气泡（引用编号、证据标签、收藏/反馈/复制/导出、顶部操作主次分层 + 更多菜单） |
| `components/EmptyState.tsx` | 三种空状态模式（onboarding/first-question/returning），根据工作区文档数和对话数动态渲染 |
| `components/ErrorBoundary.tsx` | 组件级错误边界（支持 fallback prop） |
| `hooks/useChat.ts` | SSE 流式聊天 hook（逻辑委托至 chat/ 子模块） |
| `hooks/chat/` | 聊天状态拆分：`types.ts` 类型定义、`useChatMessages.ts` 消息列表管理、`usePinnedSourcesState.ts` 来源固定/排除状态 |
| `lib/api.ts` | API 客户端（SSEParser 支持 CRLF/CR + createChatStreamAdapter） |
