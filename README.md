<div align="center">
  <h1>KnowBase</h1>
  <p>面向内网团队知识管理场景的 AI 知识库问答系统，展示 RAG 应用从文档导入、检索增强、流式问答、来源引用、权限控制到工程化部署的完整实现。</p>
  <p>
    <img src="https://img.shields.io/badge/React-19-000?style=for-the-badge&logo=react&logoColor=61DAFB" height="28" alt="React 19" />
    <img src="https://img.shields.io/badge/FastAPI-0.115-000?style=for-the-badge&logo=fastapi&logoColor=009688" height="28" alt="FastAPI" />
    <img src="https://img.shields.io/badge/LangGraph-1.2-000?style=for-the-badge&logo=langchain&logoColor=1C3C3C" height="28" alt="LangGraph" />
    <img src="https://img.shields.io/badge/Vite-TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=3178C6" height="28" alt="TypeScript" />
  </p>
</div>

![KnowBase 当前桌面界面](docs/screenshots/chat-overview.png)

当前仓库已附带一张基于真实运行环境的界面截图。

## 项目亮点

- 完整 RAG 链路：支持文档导入、切分、Embedding、混合检索、重排、生成和来源引用
- LangGraph 工作流：将问题路由、查询改写、检索、生成、质量检查和 Web Search fallback 拆成可维护节点
- SSE 流式问答：后端持续推送节点状态、token、来源和调试信息，前端实时渲染回答过程
- 后台任务系统：文件导入、URL 导入、清空工作区和重建索引通过 Redis RQ 异步执行
- 团队协作能力：支持账号登录、JWT 会话、角色权限、工作区授权、对话、书签和运行时设置
- 工程化约束：包含 OpenAPI 类型同步、结构守卫、测试、Docker Compose 和准生产安全检查

## 核心链路

```mermaid
flowchart LR
    A["上传文档 / 导入 URL"] --> B["Redis RQ 后台任务"]
    B --> C["文档解析与切分"]
    C --> D["Embedding"]
    D --> E["Chroma 向量库"]

    U["用户提问"] --> G["FastAPI SSE 接口"]
    G --> H["LangGraph 工作流"]
    H --> I["查询改写 / 混合检索 / 重排"]
    I --> J["LLM 生成与质量检查"]
    J --> K["来源引用 + 流式返回"]

    G --> L["Postgres/SQLite 业务数据"]
    L --> M["对话 / 书签 / 工作区 / 审计 / 任务"]
```

## 项目概览

KnowBase 关注的是“可持续维护的团队 RAG 应用骨架”，而不是只演示一条检索链路。当前仓库已经具备这些能力：

- SSE 流式问答，回答可附带来源片段与调试信息
- 账号密码登录、JWT 会话、固定角色和工作区授权
- 本地文件上传与公开 URL 导入，导入/清空/重建索引通过 Redis RQ 后台任务执行
- 知识库浏览、来源列表、热点片段与调试检索
- 工作区、对话、书签与运行时设置
- Postgres 业务数据入口与 SQLite 一次性导入脚本；Chroma 继续作为本地向量库
- 本地查询日志与指标面板
- OpenAPI 快照与前端生成类型的契约同步

## 重点设计

### RAG 可维护性

项目没有把检索、生成和质量检查写成单个长函数，而是通过 LangGraph 拆成问题路由、查询改写、知识库检索、Web Search fallback、回答生成和质量检查等节点。这样可以更清楚地观察每一步的输入输出，也方便后续替换检索策略或增加新的质量门禁。

### 工程化而非单次 Demo

文档导入走后台任务，避免长耗时请求阻塞 API；前后端通过 OpenAPI 快照和生成类型保持契约同步；提交前提供结构守卫、后端测试、前端测试和构建检查，目标是让项目能持续维护，而不是只跑通一次演示。

### 安全边界

URL 导入包含 SSRF 防护、响应大小限制和重定向逐跳校验；生产模式会拒绝弱 JWT、SQLite 数据库、localhost CORS 和 legacy API key；工作区用于单组织内的访问授权，不把当前实现包装成 SaaS 级多租户隔离。

## 工作区语义

“工作区”是单组织团队版的授权作用域，这里明确说明：

- 工作区会作用于对话、书签，以及知识库导入/查询时传递的 `workspace_id`
- JWT 用户访问工作区数据前会按成员角色校验；`admin` 可管理全部工作区
- 它不是多组织 SaaS 租户隔离方案，也不承诺跨组织计费、域名或数据面隔离
- 删除工作区时，对话和书签会回落到默认工作区；已导入知识库数据的迁移/清理仍需显式处理

如果你要做内网演示，可以把它理解成“单组织内的知识库授权分组”，而不是“租户级隔离”。

## 快速开始

### 前置要求

- Python 3.11+，推荐 3.12
- Node.js 20+
- `uv`
- 一个可用的 `SILICONFLOW_API_KEY`，完整问答链路需要它

### 5 分钟体验

```bash
cd backend
cp .env.example .env
# 只填必填项 SILICONFLOW_API_KEY
uv run python scripts/quickstart.py --reset
```

这个脚本会把 `examples/demo-documents/` 中的示例文档导入到隔离的 `runtime/quickstart/` 运行目录，再跑几条预置问题。只想先确认资源结构时可以运行：

```bash
cd backend
uv run python scripts/quickstart.py --dry-run
```

### 本地启动

优先使用仓库脚本：

```bash
bash scripts/dev.sh
```

Windows PowerShell:

```powershell
scripts\dev.bat
```

脚本会启动前端、后端、RQ worker，并在本机没有 Redis 监听 `6379` 时启动项目内置的 fake Redis。文件上传、URL 导入、清空工作区和重建索引都依赖这个后台任务链路。

也可以分别启动：

```bash
cd backend
uv run uvicorn src.api.main:app --reload --port 8000
```

```bash
cd backend
# 如果本机没有 Redis，可先启动开发用 fake Redis
PLAYWRIGHT_REDIS_PORT=6379 uv run python scripts/start_fake_redis.py
```

```bash
cd backend
uv run python -m src.jobs.worker
```

```bash
cd frontend
npm install
npm run dev
```

Docker 自托管环境：

```bash
cp .env.compose.example .env.compose
# 填写至少 POSTGRES_PASSWORD、JWT_SECRET、CORS_ALLOW_ORIGINS、SILICONFLOW_API_KEY
docker compose --env-file .env.compose up --build
```

Compose 会同时启动 Postgres、Redis、backend、worker 和 frontend，并把容器内 `DATABASE_URL` 显式绑定到 compose 中的 Postgres 服务。根目录 `runtime/` 与 `examples/` 会挂载到容器内，避免 Chroma、本地运行时覆盖和示例文档只存在于容器临时层。
backend 镜像以非热重载方式运行 FastAPI，frontend 镜像会先构建静态产物再通过 Vite preview 服务，并把 `/api` 请求代理到 backend；源码不会被挂载覆盖镜像内容。

启动前建议先做静态检查：

```bash
docker compose --env-file .env.compose config
```

前端默认地址为 [http://localhost:5173](http://localhost:5173)。

### 准生产安全模式

本地开发默认 `APP_ENV=development`，保留未登录和 legacy `API_KEY` 兼容路径。内网自托管准生产部署应显式设置：

```bash
APP_ENV=production
JWT_SECRET=至少 32 位的随机字符串
DATABASE_URL=postgresql+psycopg://knowbase:***@postgres/knowbase
REDIS_URL=redis://redis:6379/0
CORS_ALLOW_ORIGINS=https://knowbase.internal
```

生产模式启动时会拒绝弱 `JWT_SECRET`、SQLite `DATABASE_URL`、通配/localhost CORS，以及 legacy `API_KEY`。生产请求必须使用账号密码登录后的 JWT。

如果使用 Compose 部署，推荐直接复制根目录的 `.env.compose.example` 为 `.env.compose`，再通过 `docker compose --env-file .env.compose up --build` 启动。Compose 不依赖本地开发用的 `backend/.env`；Postgres/Redis/JWT/CORS 等变量都来自 `.env.compose`，并会显式注入 backend 与 worker 容器。

`.env.compose.example` 默认按内网自托管准生产场景给出 `APP_ENV=production`，因此 `CORS_ALLOW_ORIGINS` 不能填 `localhost`。如果你只是本机联调，可以把 `APP_ENV` 改回 `development` 后再启动。

## 质量门禁

提交前至少建议运行以下命令：

```bash
bash scripts/run-checks.sh
```

或按分步方式执行：

```bash
(cd backend && uv run pytest tests --tb=short -q)
python scripts/check-structure.py
(cd frontend && npm test)
(cd frontend && npm run build)
(cd frontend && npm run check-api-types)
```

如果后端接口或 schema 有变更，再补这两步：

```bash
(cd backend && uv run python scripts/export_openapi.py)
(cd frontend && npm run gen-api-types)
```

GitHub Actions 当前会执行：

- 后端 `pytest`（包含隔离 Postgres 16 上的 Chat 并发事务测试）
- 结构守卫 `python scripts/check-structure.py`
- 前端 `npm test`
- 前端 `npm run build`
- 前端生成类型漂移检查 `npm run check-api-types`
- Playwright E2E `cd frontend && npm run e2e`

## 契约与类型同步

仓库把 `backend/openapi.json` 视为提交态 API 快照，把 `frontend/src/shared/api/api-types.openapi.ts` 视为前端生成物。

- 当 FastAPI 路由或 Pydantic schema 改动时，先导出 `backend/openapi.json`
- 再重新生成前端 OpenAPI 类型
- CI 会阻止“后端契约已变但快照或前端类型未更新”的提交

手写 SSE 类型位于 `frontend/src/shared/api/api-types.ts`，并由后端测试校验是否与 Pydantic 模型同步。

## 结构文档

- 架构边界与依赖方向：[`docs/architecture/dependency-rules.md`](docs/architecture/dependency-rules.md)
- 后端结构说明：[`docs/architecture/backend-structure.md`](docs/architecture/backend-structure.md)
- 前端结构说明：[`docs/architecture/frontend-structure.md`](docs/architecture/frontend-structure.md)
- 产品边界与当前范围：[`docs/requirements/product-boundaries.md`](docs/requirements/product-boundaries.md)
- 运行数据策略：[`docs/operations/runtime-data-policy.md`](docs/operations/runtime-data-policy.md)
- CI 与测试矩阵：[`docs/testing/12-ci-test.md`](docs/testing/12-ci-test.md)

## 架构概览

```mermaid
flowchart LR
    A["用户提问"] --> B["SSE Chat API"]
    B --> C["LangGraph 工作流"]
    C --> D["混合检索 / 重排 / 生成 / 质量检查"]
    D --> E["Chroma + Postgres/SQLite + Redis RQ + 本地日志"]
    B --> F["React 前端"]
    F --> G["知识库浏览 / 工作区 / 书签 / 指标 / 设置"]
```

## 仓库结构

```text
KnowBase/
├── backend/               # FastAPI、LangGraph、OpenAPI、测试
├── frontend/              # React、Vite、Vitest、生成类型
├── docs/                  # architecture / requirements / testing / operations / screenshots
├── examples/              # 版本控制下的演示与预置样例
├── runtime/               # 本地运行数据（忽略提交）
├── docker/                # Docker 构建文件
└── scripts/               # 本地开发辅助脚本
```

后端唯一 Python 应用根是 `backend/`。仓库根目录不再承担 `uv sync` / `uv run` 的 Python 项目职责。

## 当前范围与已知限制

- 当前定位为内网自托管单组织团队版，不是公网 SaaS 多组织多租户方案
- 完整回答链路依赖外部模型提供方；未配置 `SILICONFLOW_API_KEY` 时无法完成真实问答
- 已有账号密码登录、JWT、固定角色和工作区授权；legacy `API_KEY` 仅保留为开发兼容路径
- 工作区是单组织内的授权作用域，不提供 SaaS 租户级隔离
- 工作区删除不会自动完成所有知识库数据的生命周期治理
- 前端 token 当前存储在 `localStorage`，适合内网演示和本地开发；更严格的生产环境可改为 HttpOnly refresh cookie + 内存 access token
- 前端部分页面和面板仍偏大，后续可以继续拆分为更细的 feature hooks 和展示组件
- SQLite/Postgres 双路径提升了本地体验，但也增加了 schema 漂移和测试矩阵成本，后续可进一步统一到 SQLAlchemy + Alembic
- RAG 质量评估已有数据集入口，后续可继续补充检索命中率、引用正确率和无证据拒答率等离线指标

## 面试讲解摘要

KnowBase 是一个内网团队知识库问答系统。我重点实现的是完整 AI 应用链路，而不是简单调用大模型 API。

用户可以上传文档或导入公开 URL，后端通过 Redis RQ 后台任务解析、切分并写入 Chroma 向量库。用户提问时，FastAPI 通过 SSE 建立流式接口，LangGraph 负责问题路由、查询改写、混合检索、重排、生成和质量检查，最终返回回答、引用来源和调试信息。

项目还实现了账号登录、JWT、工作区权限、对话历史、书签、指标、OpenAPI 类型同步、测试和 Docker Compose 部署，因此它更接近真实 AI 应用开发场景，而不是一次性的 RAG Demo。

## 贡献

协作规则、提交前检查、OpenAPI 导出和前端类型生成流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
