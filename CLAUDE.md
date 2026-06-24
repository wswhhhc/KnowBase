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

# 离线 RAG 评估
cd backend && uv run python -m src.evaluate
```

## Architecture

**KnowBase** — LangChain + LangGraph 知识库问答助手。React 前端 + FastAPI 后端前后端分离架构。

### 项目结构

```
KnowBase/
├── backend/                    # FastAPI 后端
│   ├── config/
│   │   └── settings.py         # pydantic-settings，含环境变量 → .env 映射
│   ├── src/
│   │   ├── api/                # FastAPI 路由层（main / deps / models / routes/*）
│   │   ├── graph.py            # LangGraph 工作流（图定义 + 全部节点）
│   │   ├── graph_state.py      # GraphState TypedDict + Pydantic 决策模型
│   │   ├── knowledge_base.py   # Chroma 向量库 + jieba BM25 + RRF 融合
│   │   ├── kb_models.py        # 检索结果数据类和 helper
│   │   ├── conversations.py    # 对话 CRUD（SQLite 持久化）
│   │   ├── loaders.py          # 多格式文档加载器（txt/md/pdf/docx/html + URL）
│   │   ├── web_search.py       # Tavily 联网搜索（可选）
│   │   ├── metrics.py          # 查询 JSONL 日志
│   │   ├── chat_utils.py       # 节点标签/指标记录/标题生成
│   │   └── utils.py            # 文件上传校验 + 唯一临时文件名
│   └── tests/                  # 22 个测试文件，368 个用例
├── frontend/                   # React 19 + Vite + Tailwind
│   └── src/
│       ├── components/         # ChatArea / Sidebar / BrowserPage / DashboardPage + ui/
│       ├── hooks/              # useChat（SSE 流式）/ useData / useTheme
│       └── lib/                # api.ts（全量 API 客户端）/ utils.ts
├── config/                     # 共享配置（pydantic-settings）
├── data/                       # chroma_db / checkpoints.db / conversations.db / logs
└── docs/
    └── tests/                  # 8 份测试文档（单元/集成/冒烟/边界/接口/验收/缺陷/报告）
```

### API 端点

| 端点 | 功能 |
|------|------|
| `POST /api/chat/stream` | SSE 流式聊天（事件：node/token/sources/debug/done） |
| `GET/POST/DELETE /api/conversations` | 对话 CRUD |
| `PATCH /api/conversations/:id` | 重命名 |
| `GET /api/conversations/:id/messages` | 消息列表 |
| `POST /api/conversations/:id/messages/:msg_id/feedback` | 消息反馈 |
| `GET /api/conversations/:id/export` | Markdown 导出 |
| `POST /api/documents/upload` | 文件上传（流式读取） |
| `POST /api/documents/ingest-url` | URL 导入 |
| `DELETE /api/documents/source/:name` | 删除来源 |
| `POST /api/documents/clear` | 清空知识库 |
| `GET /api/knowledge-base/stats` | 统计 |
| `GET /api/knowledge-base/chunks` | 分页浏览 |
| `GET /api/knowledge-base/sources` | 来源列表 |
| `GET /api/metrics/logs` | 查询日志 |
| `DELETE /api/metrics/logs/today` | 删除今日日志 |

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

- 包管理用 `uv`，不用 pip。`.env` 放在 `backend/.env`。
- `backend/config/settings.py` 是唯一配置入口，pydantic-settings 驱动。`CHROMA_API_KEY` 回退作为 `SILICONFLOW_API_KEY`。
- LLM 和 embedding 都通过硅基流动 OpenAI-compatible API 调用。
- Chroma 持久化在 `data/chroma_db/`；对话在 `data/conversations.db`；checkpoints 在 `data/checkpoints.db`。
- API Key 鉴权：`deps.py` 提供 `verify_api_key` 依赖，`API_KEY` 空值时跳过（本地开发无感）。
- Tavily 为可选依赖，未配 Key 时不显示在 UI 中。
- 搜索策略：`fast`（无 rerank）、`balanced`（默认、条件 rerank）、`high_quality`（必走 rerank）。
- 前端 `api.ts` 自动带 Authorization 头，后端所有写操作 + 读操作端点均受鉴权保护。

### 测试策略

**后端**：Python unittest（368 个用例）。LLM mock 用 `FakeLLM`/`FakeResponse` + `unittest.mock.patch`，Chroma mock 用 patch 替换，SQLite 用 `tempfile.TemporaryDirectory` 隔离。测试文件散列在 `tests/` 下，覆盖 graph、knowledge_base、conversations、api endpoints、loaders、utils、metrics、web_search、settings、edge cases 等模块。

**前端**：vitest + @testing-library/react（147 个用例）。SSE 用 `ReadableStream` 模拟，mock 数据在 `src/test/mocks/data.ts`。覆盖 hooks、组件渲染、交互、API 客户端。

```bash
# 后端全部
cd backend && uv run python -m unittest discover -v

# 前端全部
cd frontend && npm test
```
