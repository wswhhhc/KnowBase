# KnowBase 项目结构整理方案

## 1. 目标

这份方案的目标不是“把目录改得好看”，而是把仓库整理成一个具备以下特征的工程：

- 一眼能看懂入口、边界、数据位置和职责分层
- 前后端、脚本、文档、运行数据之间没有歧义
- CI、本地开发、Docker、测试、文档都基于同一套项目根约定
- 领域层不反向依赖 API 层，UI 页面不反向依赖应用入口
- 新人进入仓库后，不需要靠猜测理解“应该把文件放哪”

## 2. 整理总原则

### 2.1 单一事实来源

- Python 项目根只能有一个
- 运行时数据根只能有一个
- OpenAPI 快照位置只能有一个
- 前端生成类型位置只能有一个

### 2.2 装配层最薄

- `main.py` / `App.tsx` 只负责装配，不负责承载业务定义
- 类型、常量、DTO、公共模型不能挂在入口文件上

### 2.3 依赖方向单向

必须保持：

- `api -> application -> domain -> infrastructure`
- `pages -> features -> entities/shared`

禁止出现：

- `rag` / `domain` 反向依赖 `api.models`
- 页面组件反向依赖 `App.tsx`
- 核心逻辑直接依赖展示层组件或 HTTP DTO

### 2.4 运行数据与版本化样例分离

- 演示样例可以进 Git
- 数据库、向量库、日志、缓存不能进 Git
- “给程序运行用的数据”和“给仓库展示用的样例”必须物理隔离

### 2.5 文件职责单一

经验规则：

- 后端单文件超过 250 行，需要评估拆分
- 前端页面文件超过 250 行，需要评估拆分
- 一个文件里同时出现“模型定义 + IO + 业务逻辑 + 持久化 + 装配”，视为越界

## 3. 推荐的最终仓库结构

建议保留 monorepo，但明确“仓库根是总根，`backend/` 和 `frontend/` 是子应用根”。

```text
KnowBase/
├── .github/
│   └── workflows/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── .env.example
│   ├── README.md
│   ├── src/
│   │   └── knowbase/
│   │       ├── api/
│   │       ├── application/
│   │       ├── domain/
│   │       ├── infrastructure/
│   │       ├── config/
│   │       └── bootstrap/
│   ├── migrations/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── contract/
│   └── scripts/
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── README.md
│   ├── public/
│   ├── scripts/
│   ├── src/
│   │   ├── app/
│   │   ├── pages/
│   │   ├── features/
│   │   ├── entities/
│   │   ├── shared/
│   │   └── test/
│   └── coverage/
├── docs/
│   ├── architecture/
│   ├── requirements/
│   ├── testing/
│   ├── operations/
│   └── screenshots/
├── scripts/
│   ├── dev.sh
│   ├── dev.bat
│   └── run-checks.sh
├── docker/
├── examples/
│   └── demo-documents/
├── runtime/
│   ├── local/
│   ├── quickstart/
│   └── .gitkeep
├── README.md
├── CONTRIBUTING.md
└── docker-compose.yml
```

## 4. 根目录应该放什么

### 4.1 保留在根目录

- 仓库级文档：`README.md`、`CONTRIBUTING.md`
- 仓库级脚本：`scripts/dev.sh`、`scripts/dev.bat`
- 仓库级编排：`docker-compose.yml`
- CI 配置：`.github/workflows/`
- 纯展示用途样例：`examples/`
- 非代码文档：`docs/`

### 4.2 不应该继续放在根目录

- 根级 `pyproject.toml`
- 根级 `uv.lock`
- 根级 `.env`
- 根级运行数据库和日志

处理原则：

- 根目录不再充当 Python 应用根
- Python 依赖、测试入口、后端启动命令统一收敛到 `backend/`

## 5. Backend 最终分层

### 5.1 推荐目录

```text
backend/src/knowbase/
├── api/                    # HTTP 层，只处理协议问题
│   ├── routes/
│   ├── schemas/
│   ├── deps.py
│   └── app.py
├── application/            # 用例编排层
│   ├── chat/
│   ├── documents/
│   ├── settings/
│   ├── conversations/
│   └── workspaces/
├── domain/                 # 纯领域模型与规则
│   ├── chat/
│   ├── knowledge_base/
│   ├── settings/
│   └── common/
├── infrastructure/         # SQLite、Chroma、外部 API、文件系统
│   ├── persistence/
│   ├── vectorstore/
│   ├── llm/
│   ├── web_search/
│   └── loaders/
├── config/                 # 配置定义与加载
│   ├── settings.py
│   └── runtime_overrides.py
└── bootstrap/              # 应用启动装配
    ├── container.py
    └── lifespan.py
```

### 5.2 每层职责

#### `api/`

只做这些事：

- 接收 HTTP 请求
- 参数校验
- 依赖注入
- 返回响应模型
- 把领域错误映射成 HTTP 状态码

不做这些事：

- 直接写 SQL
- 直接组装 Chroma 查询
- 定义核心知识库实体

#### `application/`

负责用例编排，例如：

- `ImportDemoDocumentsUseCase`
- `StreamChatResponseUseCase`
- `UpdateRuntimeSettingsUseCase`

特点：

- 可以调用多个 repository / service
- 不关心 HTTP，也不关心 React
- 是“业务流程层”，不是协议层

#### `domain/`

这里放最稳定、最可复用的内容：

- 实体
- 值对象
- 领域服务接口
- 检索结果模型
- 业务规则

这里绝不能直接依赖：

- FastAPI
- Pydantic HTTP 响应模型
- SQLite 连接
- Chroma 实例

#### `infrastructure/`

这里承接所有技术细节：

- SQLite conversation repository
- Chroma vector store adapter
- 文档解析 loader
- Tavily web search client
- LLM client

应用层依赖它的接口，装配层决定实例化谁。

### 5.3 现有后端文件的整改建议

#### `backend/src/config/settings.py`

现状问题：

- 配置定义
- 运行时 JSON 覆盖
- public settings 组装
- secret mask
- 兼容常量导出

全部挤在一个文件。

目标拆分：

```text
config/
├── settings.py            # BaseSettings 与 typed config
├── runtime_overrides.py   # 运行时覆盖读写
├── public_settings.py     # 对 UI 暴露的安全配置映射
└── constants.py           # 仅在过渡期保留兼容常量
```

#### `backend/src/conversations.py`

现状问题：

- 会话
- 消息
- 书签
- pin state
- workspace
- migration fallback

这是典型“仓储层大杂烩”。

目标拆分：

```text
infrastructure/persistence/
├── sqlite.py
├── migrations.py
├── conversation_repository.py
├── message_repository.py
├── bookmark_repository.py
├── workspace_repository.py
└── pin_state_repository.py
```

#### `backend/src/graph/nodes.py`

现状问题：

- 查询改写
- 检索
- rerank
- web search
- 质量检查
- 答案生成
- finalize

文件过大，节点族没有分组。

目标拆分：

```text
domain/chat/
├── query_rewrite.py
├── retrieval.py
├── rerank.py
├── answer_generation.py
├── quality_check.py
├── evidence.py
└── finalization.py
```

图装配独立：

```text
application/chat/
├── graph_builder.py
├── graph_routes.py
├── graph_state.py
└── stream_chat.py
```

#### `backend/src/rag/knowledge_base.py`

现状问题：

- facade 概念是对的
- 但它现在直接依赖 API schemas，不够干净

整改要求：

- `KnowledgeBase` 只返回 domain DTO
- `api/routes/*` 再做响应模型映射

### 5.4 Backend 命名纪律

- API schema 后缀：`*Request`, `*Response`, `*Out`
- 应用用例后缀：`*UseCase`
- 仓储后缀：`*Repository`
- 基础设施适配器后缀：`*Client`, `*Store`, `*Loader`
- 领域模型：不用 `Api`、`Http`、`Fastapi` 之类词汇

## 6. Frontend 最终分层

### 6.1 推荐目录

```text
frontend/src/
├── app/                   # 应用装配、路由、provider、入口
│   ├── App.tsx
│   ├── providers.tsx
│   ├── navigation.ts
│   └── main.tsx
├── pages/                 # 页面级容器
│   ├── chat/
│   ├── browser/
│   ├── dashboard/
│   └── settings/
├── features/              # 功能切片
│   ├── chat-stream/
│   ├── knowledge-browser/
│   ├── conversations/
│   ├── bookmarks/
│   ├── workspaces/
│   └── runtime-settings/
├── entities/              # 稳定业务实体模型
│   ├── message/
│   ├── source/
│   ├── workspace/
│   └── document/
├── shared/                # 共享层
│   ├── api/
│   ├── lib/
│   ├── ui/
│   ├── hooks/
│   ├── types/
│   └── constants/
└── test/
```

### 6.2 页面与功能的关系

- `pages/` 只拼装页面
- `features/` 承载具体交互和状态逻辑
- `shared/ui/` 放通用 UI 原子组件
- `entities/` 放实体类型与展示部件

### 6.3 当前前端文件的整改建议

#### `frontend/src/App.tsx`

现状问题：

- 页面切换
- 媒体查询
- 懒加载
- workspace 同步
- highlight 行为
- mobile nav

承担过多。

目标：

- `app/App.tsx` 只做应用骨架和 provider 装配
- `app/navigation.ts` 定义 `ViewType`
- 页面切换状态抽成 `useAppNavigation`
- workspace 会话同步抽成 `useWorkspaceSession`

#### `frontend/src/shared/api/index.ts`

当前收口结果：

- 业务代码已经统一从 `shared/api` 入口消费客户端与类型
- `chat.ts`、`documents.ts`、`knowledge-base.ts` 等模块承接了原先巨石 API 文件的拆分结果
- 兼容壳文件应该删除，避免旧入口重新成为主路径

目标维持：

目标拆分：

```text
shared/api/
├── client.ts
├── errors.ts
├── sse.ts
├── chat.ts
├── conversations.ts
├── documents.ts
├── knowledge-base.ts
├── metrics.ts
├── settings.ts
├── workspaces.ts
└── bookmarks.ts
```

#### `frontend/src/hooks/useBrowserPage.ts`

现状问题：

- 筛选
- 分页
- 上传
- URL 导入
- 高亮逻辑
- hotspot
- 进度状态

目标拆分：

```text
features/knowledge-browser/
├── hooks/
│   ├── useBrowserFilters.ts
│   ├── useBrowserChunks.ts
│   ├── useBrowserUpload.ts
│   ├── useBrowserHighlight.ts
│   └── useBrowserHotspots.ts
├── components/
└── model/
```

#### `frontend/src/components/Sidebar.tsx`

现状问题：

- 导航
- 会话
- 文档
- 书签
- 工作区选择
- 弹窗

目标拆分：

- `pages` 负责布局
- `features/conversations`
- `features/bookmarks`
- `features/workspaces`
- `features/documents`

Sidebar 只做容器，不内嵌完整业务实现。

### 6.4 Frontend 命名纪律

- 页面组件：`ChatPage.tsx`, `BrowserPage.tsx`
- 功能组件：`ConversationListPanel.tsx`
- hooks：`useConversationList.ts`
- API 类型：统一从 `shared/api/types.ts` 出口
- 禁止组件从 `App.tsx` 导入类型

## 7. 数据、样例、运行产物的最终位置

### 7.1 推荐布局

```text
examples/
└── demo-documents/         # 版本控制下的演示资料

runtime/
├── local/                  # 默认本地运行数据
│   ├── chroma_db/
│   ├── conversations.db
│   ├── checkpoints.db
│   └── rag_logs/
└── quickstart/             # quickstart 专用运行数据
```

### 7.2 强制规则

- `examples/` 允许提交
- `runtime/` 整体忽略提交
- quickstart 从 `examples/demo-documents/` 复制或读取样例
- 默认应用运行目录和 quickstart 运行目录不能混用

### 7.3 为什么这样更整洁

因为一眼就能区分：

- `examples` 是给人看的
- `runtime` 是给程序跑的

而不是像现在这样 `root/data` 和 `backend/data` 两边同时存在。

## 8. 文档体系应该怎么摆

建议改成按主题归档，而不是平铺文件。

```text
docs/
├── architecture/
│   ├── system-overview.md
│   ├── backend-structure.md
│   ├── frontend-structure.md
│   └── dependency-rules.md
├── requirements/
│   └── product-boundaries.md
├── testing/
│   ├── 01-unit-test.md
│   ├── 02-integration-test.md
│   └── ...
├── operations/
│   ├── local-dev.md
│   ├── release-checklist.md
│   └── runtime-data-policy.md
└── screenshots/
```

同时要求：

- `README.md` 只讲“怎么理解项目、怎么启动、怎么验证”
- 详细结构规范放 `docs/architecture/`
- 详细测试规范放 `docs/testing/`

## 9. 脚本与 CI 的归位规则

### 9.1 根脚本

只放跨应用脚本：

- 同时启动前后端
- 跑全仓检查
- Docker 编排

### 9.2 子应用脚本

- `backend/scripts/` 只放后端专用脚本
- `frontend/scripts/` 只放前端专用脚本

### 9.3 CI 约定

CI 必须明确：

- 后端工作目录是 `backend/`
- 前端工作目录是 `frontend/`
- 根目录不再执行 `uv sync`

推荐执行方式：

- `cd backend && uv sync && uv run pytest`
- `cd frontend && npm ci && npm test && npm run build`

## 10. 当前仓库到目标结构的迁移方案

按阶段推进，不要一次性硬改。

### Phase 1: 统一根约定

目标：

- 明确 `backend/` 是唯一 Python 应用根
- 删除根级 Python 项目元数据

动作：

1. 以 `backend/pyproject.toml` 为唯一保留版本
2. 删除根级 `pyproject.toml`
3. 删除根级 `uv.lock`
4. 修改 CI、README、脚本，统一使用 `cd backend`
5. 根级 `.env` 废弃，只保留 `backend/.env`

验收：

- 根目录运行说明不再出现 `uv sync`
- CI 不再从根目录安装 Python 依赖

### Phase 2: 统一数据根

目标：

- 只保留一套运行数据目录

推荐结论：

- 版本化示例迁移到 `examples/demo-documents/`
- 运行数据统一迁移到 `runtime/local/`

动作：

1. 改 `settings.py` 默认路径
2. 改 quickstart 脚本读取路径
3. 改 demo import 读取路径
4. 更新 `.gitignore`
5. 清理 `backend/data/` 与根级 `data/` 的双轨结构

验收：

- quickstart、import-demo、默认启动都使用统一路径策略

### Phase 3: 拆后端边界

目标：

- 清除 `rag -> api.models` 的反向依赖

动作：

1. 提取 domain DTO
2. API schema 改为单独映射层
3. 拆 `conversations.py`
4. 拆 `graph/nodes.py`
5. 拆 `settings.py`

验收：

- `domain/`、`rag/` 不再导入 `api/`
- 核心逻辑可脱离 FastAPI 独立测试

### Phase 4: 拆前端边界

目标：

- `App.tsx` 薄化
- `api.ts` 解体
- 大页面状态按 feature 拆开

动作：

1. 提取 `ViewType` 到 `app/navigation.ts`
2. API client 拆模块
3. `useBrowserPage` 按功能拆 hooks
4. `Sidebar` 拆成功能面板
5. 页面目录迁入 `pages/`

验收：

- 组件不再从 `App.tsx` 导入类型
- `shared/api/` 不再是单文件巨石

### Phase 5: 文档和治理收口

目标：

- 让目录纪律可长期维持

动作：

1. 更新 `README.md`
2. 更新 `CONTRIBUTING.md`
3. 增加 `docs/architecture/dependency-rules.md`
4. 增加结构 lint 规则或 reviewer checklist

验收：

- 新人能仅凭 README + architecture docs 理解项目

## 11. 文件迁移对照表

### 建议删除

- 根级 `pyproject.toml`
- 根级 `uv.lock`
- 根级 `.env`

### 建议迁移

- `data/samples/demo/*` -> `examples/demo-documents/`
- `data/sample_*.txt` -> `examples/preset-documents/`
- 运行数据库/日志 -> `runtime/local/`

### 建议拆分

- `backend/src/conversations.py`
- `backend/src/graph/nodes.py`
- `backend/src/config/settings.py`
- `frontend/src/shared/api/index.ts`
- `frontend/src/hooks/useBrowserPage.ts`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/App.tsx`

## 12. 以后新增文件时的落位规则

可以直接按下面判断：

### 后端

- 是 HTTP 请求/响应模型：放 `api/schemas/`
- 是接口处理器：放 `api/routes/`
- 是业务流程编排：放 `application/`
- 是核心规则或实体：放 `domain/`
- 是 SQLite/Chroma/外部 API：放 `infrastructure/`
- 是启动组装：放 `bootstrap/`

### 前端

- 是页面：放 `pages/`
- 是某个业务功能：放 `features/`
- 是稳定实体类型/展示：放 `entities/`
- 是基础组件/工具/API 客户端：放 `shared/`
- 是应用入口/Provider/导航：放 `app/`

## 13. 你要的“整洁感”最终来自什么

真正让项目显得整洁有纪律，不是目录层级多，而是下面 5 件事同时成立：

1. 任何文件都有明确归属理由
2. 任何依赖都遵循固定方向
3. 任何运行数据都有唯一位置
4. 任何入口都只有一个事实来源
5. 任何大文件一旦越界，就有明确拆分落点

如果你照这个方案执行，仓库会从“能跑，但边界摇摆”变成“结构稳定、可扩展、可审查”的状态。

## 14. 最后的定案建议

对于 KnowBase，我建议你采用下面这组最终定案，不要再摇摆：

- 仓库类型：monorepo
- Python 应用根：`backend/`
- Node 应用根：`frontend/`
- 演示样例根：`examples/`
- 运行数据根：`runtime/`
- 后端包根：`backend/src/knowbase/`
- 前端源码根：`frontend/src/{app,pages,features,entities,shared}`
- API 契约快照：`backend/openapi.json`
- 前端生成类型：`frontend/src/shared/api/api-types.openapi.ts`

这套定案是目前最适合你这个项目的，不花哨，但纪律性最强。
