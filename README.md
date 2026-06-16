# KnowBase

基于 LangChain + LangGraph 的知识库问答助手。**React 前端 + FastAPI 后端** 前后端分离架构，Chroma 本地向量库 + 候选集 BM25 混合检索，通过硅基流动 API 调用 LLM 和 embedding 模型。

## 功能

- **双前端**：React 杂志编辑风 UI（默认） + Streamlit 经典界面（兼容）
- 预设知识库问答和 `.txt` / `.md` / `.pdf` / `.docx` / `.html` 动态上传
- URL 一键导入网页内容
- SSE 流式输出回答，边生成边展示
- **RAG Debug 面板：** 每条消息可展开查看检索链路详情（召回文档、分数、精排、质量检查）
- 查询改写 → 候选集混合检索 → 条件式 LLM 精排 → 生成回答 → 分层质量检查
- 联网搜索兜底（可选 Tavily）
- 检索策略：fast / balanced / high_quality
- **自适应向量召回：** 根据文档总数动态调整召回候选数（30~100）
- 邻居 chunk 上下文补全 + 标题追踪
- **热点追踪：** 知识库浏览页按被检索次数高亮显示热门片段
- **深度阅读模式：** 切换知识库浏览为内容优先的深度阅读视图
- 知识库内容浏览（杂志藏书阁风格网格，支持分页）
- **对话标题 LLM 自动生成：** 根据问题语义自动生成标题
- 指标面板（编辑式数据看板，耗时分布/质量通过率/查询日志）
- 浅色/深色模式切换
- 离线 RAG 评估脚本

## 快速开始

### 1. 配置文件

创建或编辑 `.env`：

```env
SILICONFLOW_API_KEY=你的硅基流动密钥
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
EMBEDDING_MODEL=BAAI/bge-m3

# 可选
TAVILY_API_KEY=tvly-xxx            # 联网搜索兜底
```

### 2. 启动开发环境（推荐）

```bash
# 一键启动（后端 8000 + 前端 5173）
bash scripts/dev.sh          # macOS / Linux
scripts\dev.bat              # Windows

# 或分别启动：
cd backend && uv run uvicorn src.api.main:app --reload --port 8000
cd frontend && npm run dev
```

打开 http://localhost:5173

### 3. 旧版 Streamlit（可选）

```bash
uv run streamlit run src/app.py
```

## 项目结构

```
KnowBase/
├── backend/                    # FastAPI 后端
│   ├── config/                 # pydantic-settings 配置
│   ├── src/
│   │   ├── api/                # REST API 路由层
│   │   │   ├── main.py         # 应用入口 + CORS
│   │   │   ├── deps.py         # 依赖注入
│   │   │   ├── models.py       # Pydantic 模型
│   │   │   └── routes/
│   │   │       ├── chat.py           # SSE 流式聊天
│   │   │       ├── conversations.py  # 对话 CRUD
│   │   │       ├── documents.py      # 文档上传/URL导入
│   │   │       ├── knowledge_base.py # 知识库浏览
│   │   │       └── metrics.py        # 查询日志
│   │   ├── graph.py            # LangGraph 工作流
│   │   ├── knowledge_base.py   # Chroma + BM25 核心
│   │   ├── conversations.py    # 对话管理模块
│   │   ├── loaders.py          # 文档加载器
│   │   ├── web_search.py       # Tavily 搜索
│   │   ├── metrics.py          # JSONL 日志
│   │   └── utils.py            # 工具函数
│   └── tests/
├── frontend/                   # React + Vite + Tailwind 前端
│   └── src/
│       ├── components/
│       │   ├── ui/             # shadcn/ui 组件
│       │   ├── ChatArea.tsx    # 对话界面
│       │   ├── Sidebar.tsx     # 侧栏导航
│       │   ├── BrowserPage.tsx # 知识库浏览
│       │   └── DashboardPage.tsx # 指标面板
│       ├── hooks/
│       │   ├── useChat.ts      # SSE 流式聊天 hook
│       │   ├── useData.ts      # 数据管理 hook
│       │   └── useTheme.ts     # 主题切换 hook
│       └── lib/
│           ├── api.ts          # API 客户端
│           └── utils.ts        # 工具函数
├── config/                     # 共享配置
├── data/                       # 共享数据（chroma/checkpoints/logs）
└── scripts/                    # 启动脚本
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

## 测试

```bash
cd backend && uv run python -m unittest discover -s tests

# 离线评估
cd backend && uv run python -m src.evaluate
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | React 19 + TypeScript |
| 构建工具 | Vite 6 |
| UI 组件 | shadcn/ui + Radix + Tailwind CSS |
| 动效 | framer-motion |
| 字体 | Instrument Serif / Inter Tight / JetBrains Mono |
| 后端框架 | FastAPI + uvicorn |
| 流式传输 | SSE (sse-starlette) |
| AI 引擎 | LangChain + LangGraph |
| 向量库 | Chroma (本地) |
| 搜索引擎 | BM25 (jieba + rank-bm25) |
| 检索融合 | RRF 倒数排序融合 |
