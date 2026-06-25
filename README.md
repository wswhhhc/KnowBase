# KnowBase

基于 LangChain + LangGraph 的知识库问答助手。**React 前端 + FastAPI 后端** 前后端分离架构，Chroma 本地向量库 + 候选集 BM25 混合检索，通过硅基流动 API 调用 LLM 和 embedding 模型。

## 功能

- **杂志编辑风 React UI**（Streamlit 旧版已移除）
- 预设知识库问答和 `.txt` / `.md` / `.pdf` / `.docx` / `.html` 动态上传
- URL 一键导入网页内容
- **工作区系统** — 多工作区管理，每个工作区独立对话和书签
- **书签收藏** — 知识库浏览时收藏片段，跨工作区管理
- **API Key 鉴权** — 写操作端点受 Bearer Token 保护，前端自动带 Authorization 头。空 `API_KEY` 时跳过鉴权，本地开发无感
- SSE 流式输出回答，边生成边展示，支持引用编号 `[1]` 标记来源
- **引用编号系统** — LLM 回答用 `[1]`、`[2]` 编号标注来源，前端渲染为交互式引用标签
- **RAG Debug 面板** — 每条消息可展开查看检索链路详情（召回文档、分数、精排、质量检查）
- 查询改写 → 候选集混合检索 → 条件式 LLM 精排 → 生成回答 → 分层质量检查
- 联网搜索兜底（可选 Tavily）
- 检索策略：fast / balanced / high_quality / deep
- **自适应向量召回** — 根据文档总数动态调整召回候选数（30~100）
- 邻居 chunk 上下文补全 + 标题追踪
- **热点追踪** — 知识库浏览页按被检索次数高亮显示热门片段
- **消息反馈** — ThumbsUp/ThumbsDown 持结构化原因选择
- **来源固定与排除** — 来源卡片支持固定和排除，跨消息状态保持
- **重答与简洁模式** — 回答底部「重新回答」「更简洁」「继续追问」
- **引用直达原文** — 点击 `[1]` 跳转知识库页高亮对应片段
- **上传后建议问题** — 文档导入后 AI 生成可点击的示例问题
- **首次使用引导** — 空状态显示三步路径（上传→提问→查看来源）
- **无答案兜底** — 四种失败场景显示明确指导 + 快捷操作
- **证据可信度解释** — 强/中/弱标签带 tooltip 解释证据构成
- 知识库内容浏览（杂志藏书阁风格网格，支持分页 + 懒加载）
- **对话标题 LLM 自动生成** — 根据问题语义自动生成标题
- 指标面板（编辑式数据看板，耗时分布/质量通过率/查询日志）
- **移动端适配** — 抽屉式侧栏 + 底部导航栏 + 响应式头部
- **SSE 节流** — 高频 token 更新时合并渲染
- **骨架屏复用** — 统一的 SkeletonCard/SkeletonGrid 组件
- **prefers-reduced-motion 支持** — 无障碍动画控制
- 浅色/深色模式切换
- 离线 RAG 评估脚本

## 快速开始

### 1. 配置文件

创建或编辑 `backend/.env`：

```env
SILICONFLOW_API_KEY=你的硅基流动密钥
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
EMBEDDING_MODEL=BAAI/bge-m3

# 可选
TAVILY_API_KEY=tvly-xxx            # 联网搜索兜底
API_KEY=your-secret-key             # API 鉴权（空值=跳过，本地开发无感）
LANGSMITH_API_KEY=lsv2-xxx          # LangSmith 追踪
```

### 2. 启动开发环境

```bash
# 一键启动（后端 8000 + 前端 5173）
bash scripts/dev.sh          # macOS / Linux
scripts\dev.bat              # Windows

# 或分别启动：
cd backend && uv run uvicorn src.api.main:app --reload --port 8000
cd frontend && npm run dev
```

打开 http://localhost:5173

## 项目结构

```
KnowBase/
├── backend/                    # FastAPI 后端
│   ├── config/
│   │   └── settings.py         # pydantic-settings 配置
│   ├── src/
│   │   ├── api/                # REST API 路由层
│   │   │   ├── main.py         # 应用入口 + CORS + lifespan（预设文档加载）
│   │   │   ├── deps.py         # 依赖注入（lru_cache 单例 KnowledgeBase）
│   │   │   ├── models.py       # Pydantic 模型
│   │   │   └── routes/
│   │   │       ├── chat.py           # SSE 流式聊天
│   │   │       ├── conversations.py  # 对话 CRUD
│   │   │       ├── documents.py      # 文档上传/URL导入
│   │   │       ├── knowledge_base.py # 知识库浏览
│   │   │       ├── metrics.py        # 查询日志
│   │   │       ├── workspaces.py     # 工作区 CRUD
│   │   │       └── bookmarks.py      # 书签 CRUD
│   │   ├── graph.py            # LangGraph 图定义
│   │   ├── graph_nodes.py      # 工作流节点函数
│   │   ├── graph_routing.py    # 条件路由函数
│   │   ├── graph_utils.py      # 工作流工具函数
│   │   ├── graph_state.py      # 工作流状态/Pydantic 模型
│   │   ├── knowledge_base.py   # 门面类，内拆 IngestionService / Retriever / HotspotTracker
│   │   ├── kb_models.py        # 检索结果/FusionScore/helper
│   │   ├── conversations.py    # 对话管理 + 工作区 + 书签 CRUD
│   │   ├── loaders.py          # 文档加载器
│   │   ├── web_search.py       # Tavily 搜索
│   │   ├── metrics.py          # JSONL 日志
│   │   ├── chat_utils.py       # 聊天路由辅助（标题生成/指标/NODE_LABELS）
│   │   └── utils.py            # 工具函数（含流式上传）
│   └── tests/                  # 28 个测试文件，400 个用例
├── frontend/                   # React + Vite + Tailwind 前端
│   └── src/
│       ├── components/
│       │   ├── sidebar/        # ConversationList / DocumentPanel / KBSummary / DashboardSummary
│       │   ├── ui/             # shadcn/ui 组件（含 SkeletonCard/SkeletonGrid）
│       │   ├── ChatArea.tsx    # 对话界面（含搜索策略选择器）
│       │   ├── Sidebar.tsx     # 侧栏导航（布局 + 视图切换 + 主题切换）
│       │   ├── BrowserPage.tsx # 知识库浏览（含分页懒加载 + 书签）
│       │   ├── DashboardPage.tsx # 指标面板
│       │   ├── EmptyState.tsx  # 空状态引导
│       │   ├── MessageBubble.tsx # 消息气泡（引用/反馈/来源）
│       │   └── DebugPanel.tsx  # RAG 调试面板
│       ├── hooks/
│       │   ├── useChat.ts      # SSE 流式聊天 hook（来源状态管理 + 重答）
│       │   ├── useData.ts      # 数据管理 hook
│       │   └── useTheme.ts     # 主题切换 hook
│       └── lib/
│           ├── api.ts          # API 客户端 + SSEParser + createChatStreamAdapter
│           ├── api-types.ts    # 类型定义
│           └── utils.ts        # 工具函数
├── docs/
│   └── tests/                  # 12 份测试文档
└── scripts/                    # 一键启动脚本
```

## LangGraph 工作流

```text
用户提问
  → 问题路由（LLM 分类 + 正则兜底）
  → 查询改写（结合历史）/ 会话记忆 / 会话总结 / 模糊提示
  → 候选集混合检索（向量召回 30 条 → 候选 BM25 → RRF 融合）
  → 条件式 LLM 精排（分数差距大/短问题跳过）
  → 生成回答（带邻居 chunk 上下文 + 标题链）
  → 分层质量检查（规则层 → LLM 审核）
  → 不合格 → 联网搜索 / 扩检索重试 → 重新生成
```

## API 端点

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
| `GET /api/knowledge-base/config` | KB 配置 |
| `GET /api/knowledge-base/hotspots` | 热点追踪 |
| `GET /api/metrics/logs` | 查询日志 |
| `DELETE /api/metrics/logs/today` | 删除今日日志 |
| `GET/POST/PATCH/DELETE /api/workspaces` | 工作区 CRUD |
| `GET/POST/DELETE /api/bookmarks` | 书签 CRUD |
| `GET /api/health` | 健康检查 |

## 测试

### 后端测试（Python unittest，28 文件，400 用例）
```bash
cd backend

# 运行全部
uv run python -m unittest discover -v

# 测试分类
uv run python -m unittest tests.test_api_endpoints -v       # 接口测试（29用例）
uv run python -m unittest tests.test_edge_cases -v          # 边界测试（18用例）
uv run python -m unittest tests.test_integration_graph_kb -v  # 集成测试（22用例）
uv run python -m unittest tests.test_smoke -v               # 冒烟测试（10用例）
uv run python -m unittest tests.test_graph -v               # 工作流测试
uv run python -m unittest tests.test_knowledge_base -v      # 知识库测试（65用例）
uv run python -m unittest tests.test_conversations -v       # 对话管理测试
uv run python -m unittest tests.test_chat_route -v          # 聊天路由集成测试
uv run python -m unittest tests.test_routing -v             # 路由分类测试
```

### 前端测试（vitest，18 文件，160 用例）
```bash
cd frontend
npm test               # 运行一次
npm run test:watch     # 监听模式
npm run test:coverage  # 覆盖率
```

### 测试文档

详见 [docs/tests/](docs/tests/)：

| 文档 | 内容 |
|------|------|
| [01-unit-test.md](docs/tests/01-unit-test.md) | 单元测试用例清单 |
| [02-integration-test.md](docs/tests/02-integration-test.md) | 跨模块集成测试 |
| [03-smoke-test.md](docs/tests/03-smoke-test.md) | 核心功能冒烟测试 |
| [04-edge-test.md](docs/tests/04-edge-test.md) | P2 边界/异常测试 |
| [05-api-test.md](docs/tests/05-api-test.md) | API 端点全覆盖 |
| [06-acceptance-test.md](docs/tests/06-acceptance-test.md) | 14 个 E2E 用户场景 |
| [07-defect-report.md](docs/tests/07-defect-report.md) | 缺陷报告模板 |
| [08-test-report.md](docs/tests/08-test-report.md) | 测试报告模板 |
| [09-performance-test.md](docs/tests/09-performance-test.md) | 性能/负载测试 |
| [10-security-test.md](docs/tests/10-security-test.md) | 安全测试 |
| [11-e2e-test.md](docs/tests/11-e2e-test.md) | Playwright E2E 测试 |
| [12-ci-test.md](docs/tests/12-ci-test.md) | CI 配置 |

### 离线评估

```bash
cd backend && uv run python -m src.evaluate
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | React 19 + TypeScript |
| 构建工具 | Vite 6 |
| UI 组件 | shadcn/ui + Radix + Tailwind CSS |
| 动效 | framer-motion |
| 图标 | lucide-react |
| 字体 | Instrument Serif / Inter Tight / JetBrains Mono |
| 后端框架 | FastAPI + uvicorn |
| 流式传输 | SSE (sse-starlette) |
| AI 引擎 | LangChain + LangGraph |
| 向量库 | Chroma (本地) |
| 搜索引擎 | BM25 (jieba + rank-bm25) |
| 检索融合 | RRF 倒数排序融合 |
| 追踪 | LangSmith（可选） |
