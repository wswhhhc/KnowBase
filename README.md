# KnowBase

<div align="center">

本地优先的知识库问答助手，采用 **React + FastAPI** 前后端分离架构，基于 **LangChain + LangGraph** 构建 RAG 工作流。  
支持多工作区、书签收藏、来源追踪、RAG 调试和流式回答，兼顾可用性与工程可维护性。

<p>
  <img src="https://img.shields.io/badge/React-19-111827?style=for-the-badge&logo=react" alt="React 19" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-065f46?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-RAG%20Workflow-1f2937?style=for-the-badge" alt="LangGraph" />
  <img src="https://img.shields.io/badge/Chroma-Local%20Vector%20DB-4c1d95?style=for-the-badge" alt="Chroma" />
  <img src="https://img.shields.io/badge/TypeScript-Vite%206-0f766e?style=for-the-badge&logo=typescript" alt="TypeScript + Vite" />
</p>

<p>
  <a href="#功能亮点">功能亮点</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#项目结构">项目结构</a> •
  <a href="#rag-工作流">RAG 工作流</a> •
  <a href="#测试">测试</a> •
  <a href="#技术栈">技术栈</a>
</p>

</div>

> [!TIP]
> 如果你想要一个带现代前端体验的本地知识库，而不是只有检索链路没有产品化交互的 demo，这个项目就是为此设计的。

## 功能亮点

### 产品体验

| 模块 | 能力 |
|------|------|
| 对话体验 | SSE 流式输出，支持引用编号 `[1]`、重新回答、更简洁、继续追问 |
| 知识导入 | 支持 `.txt` / `.md` / `.pdf` / `.docx` / `.html` 上传，以及 URL 一键导入 |
| 工作区系统 | 多工作区隔离管理，每个工作区拥有独立对话和书签 |
| 知识浏览 | 杂志式藏书阁布局，支持分页、懒加载、热点高亮 |
| 可解释性 | 交互式来源标签、证据可信度解释、点击引用直达原文 |
| 调试能力 | 内置 RAG Debug 面板，可查看召回、精排、质量检查全链路 |

### RAG 能力

- 查询改写、会话记忆、会话总结、模糊提示协同工作
- Chroma 本地向量检索 + BM25 候选召回 + RRF 融合排序
- 条件式 LLM 精排，减少不必要的高成本步骤
- 自适应向量召回，按文档规模动态调整候选数（30 到 100）
- 邻居 chunk 上下文补全 + 标题追踪，提升回答连贯性
- 质量检查失败后，可触发联网搜索兜底或扩检索重试

### 前端体验

- 杂志编辑风 React UI，已移除旧版 Streamlit 界面
- 移动端适配：抽屉侧栏 + 底部导航 + 响应式头部
- 来源固定与排除，状态跨消息保持
- 上传后自动生成建议问题，帮助用户快速起问
- 首次使用引导、无答案兜底、骨架屏复用、`prefers-reduced-motion` 支持
- 浅色 / 深色主题切换

## 架构速览

| 层 | 说明 |
|----|------|
| 前端 | React 19 + TypeScript + Vite + Tailwind，负责对话、知识浏览、调试和指标界面 |
| 后端 | FastAPI 提供 REST API 与 SSE 流式响应 |
| 工作流 | LangGraph 编排查询改写、检索、精排、生成、质量检查 |
| 存储 | Chroma 本地向量库 + JSONL 查询日志 |
| 检索 | 向量召回、BM25、RRF 融合、条件式重排 |
| 外部能力 | 硅基流动 API 提供 LLM 与 Embedding；Tavily 可选兜底联网搜索 |

## 快速开始

### 1. 配置环境变量

创建或编辑 `backend/.env`：

```env
SILICONFLOW_API_KEY=你的硅基流动密钥
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
EMBEDDING_MODEL=BAAI/bge-m3

# 可选
TAVILY_API_KEY=tvly-xxx
API_KEY=your-secret-key
LANGSMITH_API_KEY=lsv2-xxx
```

> [!NOTE]
> `API_KEY` 为空时会跳过 Bearer Token 鉴权，适合本地开发。

### 2. 一键启动

```bash
# macOS / Linux
bash scripts/dev.sh

# Windows
scripts\dev.bat
```

默认启动后端 `8000` 和前端 `5173`。  
打开 [http://localhost:5173](http://localhost:5173)。

### 3. 分别启动前后端

```bash
# backend
cd backend
uv run uvicorn src.api.main:app --reload --port 8000
```

```bash
# frontend
cd frontend
npm run dev
```

## 使用流程

1. 上传本地文档或导入网页内容
2. 在工作区中发起问题
3. 通过引用编号查看证据来源
4. 必要时展开 Debug 面板检查检索链路
5. 收藏高价值片段到书签，跨对话继续复用

## RAG 工作流

```mermaid
flowchart LR
    A["用户提问"] --> B["问题路由<br/>LLM 分类 + 正则兜底"]
    B --> C["查询改写 / 会话记忆 / 会话总结"]
    C --> D["候选集混合检索<br/>向量召回 + BM25 + RRF"]
    D --> E["条件式 LLM 精排"]
    E --> F["生成回答<br/>邻居 chunk 上下文 + 标题链"]
    F --> G["分层质量检查<br/>规则层 + LLM 审核"]
    G -->|通过| H["流式返回答案与来源"]
    G -->|不通过| I["联网搜索或扩检索重试"]
    I --> F
```

### 检索策略

项目支持四种检索策略：

- `fast`
- `balanced`
- `high_quality`
- `deep`

## 核心能力清单

<details>
<summary><strong>展开查看完整能力列表</strong></summary>

- 预设知识库问答和动态上传
- URL 一键导入网页内容
- API Key 鉴权，前端自动附带 Authorization 头
- 引用编号系统与交互式引用标签
- RAG Debug 面板
- 联网搜索兜底（可选 Tavily）
- 热点追踪
- 消息反馈（ThumbsUp / ThumbsDown）
- 来源固定与排除
- 重答与简洁模式
- 引用直达原文
- 上传后建议问题
- 首次使用引导
- 无答案兜底
- 证据可信度解释
- 自动生成对话标题
- 指标面板
- SSE 节流
- 骨架屏复用
- 无障碍动画控制

</details>

## 项目结构

```text
KnowBase/
├── backend/                    # FastAPI 后端
│   ├── config/
│   │   └── settings.py         # pydantic-settings 配置
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py         # 应用入口 + CORS + lifespan
│   │   │   ├── deps.py         # 依赖注入
│   │   │   ├── models.py       # Pydantic 模型
│   │   │   └── routes/
│   │   │       ├── chat.py
│   │   │       ├── conversations.py
│   │   │       ├── documents.py
│   │   │       ├── knowledge_base.py
│   │   │       ├── metrics.py
│   │   │       ├── workspaces.py
│   │   │       └── bookmarks.py
│   │   ├── graph.py
│   │   ├── graph_nodes.py
│   │   ├── graph_routing.py
│   │   ├── graph_utils.py
│   │   ├── graph_state.py
│   │   ├── knowledge_base.py   # 门面类，内拆 IngestionService / Retriever / HotspotTracker
│   │   ├── kb_models.py
│   │   ├── conversations.py
│   │   ├── loaders.py
│   │   ├── web_search.py
│   │   ├── metrics.py
│   │   ├── chat_utils.py
│   │   └── utils.py
│   └── tests/                  # 28 个测试文件，400 个用例
├── frontend/                   # React + Vite + Tailwind 前端
│   └── src/
│       ├── components/
│       │   ├── sidebar/
│       │   ├── ui/
│       │   ├── ChatArea.tsx
│       │   ├── Sidebar.tsx
│       │   ├── BrowserPage.tsx
│       │   ├── DashboardPage.tsx
│       │   ├── EmptyState.tsx
│       │   ├── MessageBubble.tsx
│       │   └── DebugPanel.tsx
│       ├── hooks/
│       │   ├── useChat.ts
│       │   ├── useData.ts
│       │   └── useTheme.ts
│       └── lib/
│           ├── api.ts
│           ├── api-types.ts
│           └── utils.ts
├── docs/
│   └── tests/
└── scripts/                    # 一键启动脚本
```

## API 端点

### 对话与消息

| 端点 | 功能 |
|------|------|
| `POST /api/chat/stream` | SSE 流式聊天（`node` / `token` / `sources` / `debug` / `done`） |
| `GET/POST/DELETE /api/conversations` | 对话 CRUD |
| `PATCH /api/conversations/:id` | 对话重命名 |
| `GET /api/conversations/:id/messages` | 获取消息列表 |
| `POST /api/conversations/:id/messages/:msg_id/feedback` | 消息反馈 |
| `GET /api/conversations/:id/export` | Markdown 导出 |

### 文档与知识库

| 端点 | 功能 |
|------|------|
| `POST /api/documents/upload` | 文件上传（流式读取） |
| `POST /api/documents/ingest-url` | URL 导入 |
| `DELETE /api/documents/source/:name` | 删除来源 |
| `POST /api/documents/clear` | 清空知识库 |
| `GET /api/knowledge-base/stats` | 统计信息 |
| `GET /api/knowledge-base/chunks` | 分页浏览知识片段 |
| `GET /api/knowledge-base/sources` | 来源列表 |
| `GET /api/knowledge-base/config` | 知识库配置 |
| `GET /api/knowledge-base/hotspots` | 热点追踪 |

### 工作区与指标

| 端点 | 功能 |
|------|------|
| `GET/POST/PATCH/DELETE /api/workspaces` | 工作区 CRUD |
| `GET/POST/DELETE /api/bookmarks` | 书签 CRUD |
| `GET /api/metrics/logs` | 查询日志 |
| `DELETE /api/metrics/logs/today` | 删除今日日志 |
| `GET /api/health` | 健康检查 |

## 测试

### 后端测试

Python `unittest`，共 **28 个测试文件 / 400 个用例**。

```bash
cd backend

uv run python -m unittest discover -v
uv run python -m unittest tests.test_api_endpoints -v
uv run python -m unittest tests.test_edge_cases -v
uv run python -m unittest tests.test_integration_graph_kb -v
uv run python -m unittest tests.test_smoke -v
uv run python -m unittest tests.test_graph -v
uv run python -m unittest tests.test_knowledge_base -v
uv run python -m unittest tests.test_conversations -v
uv run python -m unittest tests.test_chat_route -v
uv run python -m unittest tests.test_routing -v
```

### 前端测试

Vitest，共 **18 个测试文件 / 160 个用例**。

```bash
cd frontend

npm test
npm run test:watch
npm run test:coverage
```

### 测试文档

详见 [docs/tests/](docs/tests/)：

| 文档 | 内容 |
|------|------|
| [01-unit-test.md](docs/tests/01-unit-test.md) | 单元测试用例清单 |
| [02-integration-test.md](docs/tests/02-integration-test.md) | 跨模块集成测试 |
| [03-smoke-test.md](docs/tests/03-smoke-test.md) | 核心功能冒烟测试 |
| [04-edge-test.md](docs/tests/04-edge-test.md) | P2 边界 / 异常测试 |
| [05-api-test.md](docs/tests/05-api-test.md) | API 端点全覆盖 |
| [06-acceptance-test.md](docs/tests/06-acceptance-test.md) | 14 个 E2E 用户场景 |
| [07-defect-report.md](docs/tests/07-defect-report.md) | 缺陷报告模板 |
| [08-test-report.md](docs/tests/08-test-report.md) | 测试报告模板 |
| [09-performance-test.md](docs/tests/09-performance-test.md) | 性能 / 负载测试 |
| [10-security-test.md](docs/tests/10-security-test.md) | 安全测试 |
| [11-e2e-test.md](docs/tests/11-e2e-test.md) | Playwright E2E 测试 |
| [12-ci-test.md](docs/tests/12-ci-test.md) | CI 配置 |

### 离线评估

```bash
cd backend
uv run python -m src.evaluate
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | React 19 + TypeScript |
| 构建工具 | Vite 6 |
| UI 组件 | shadcn/ui + Radix UI + Tailwind CSS |
| 动效 | framer-motion |
| 图标 | lucide-react |
| 字体 | Instrument Serif / Inter Tight / JetBrains Mono |
| 后端框架 | FastAPI + uvicorn |
| 流式传输 | SSE (`sse-starlette`) |
| AI 工作流 | LangChain + LangGraph |
| 向量库 | Chroma（本地） |
| 搜索引擎 | BM25（`jieba` + `rank-bm25`） |
| 检索融合 | RRF 倒数排序融合 |
| 追踪 | LangSmith（可选） |

## 开发说明

- 前端目录见 [frontend/](frontend/)
- 后端目录见 [backend/](backend/)
- 测试文档见 [docs/tests/](docs/tests/)
- 一键脚本见 [scripts/](scripts/)

---

如果你正在把它作为一个可继续演进的 RAG 产品骨架，这个 README 现在应该更接近你希望别人第一次打开仓库时看到的样子。
