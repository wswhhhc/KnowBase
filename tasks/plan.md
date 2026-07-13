# KnowBase 代码结构优化实施方案

## 目标

在不改变现有 API、UI 行为、数据格式和兼容路径的前提下，降低几个结构热点的职责密度，使路由、交互状态与展示代码各自保持单一职责，并用结构守卫防止后续回退。

本轮不是重写项目。优化范围按优先级限定为：

1. `backend/src/api/routes/documents.py`
2. `frontend/src/components/sidebar/DocumentPanel.tsx`
3. `frontend/src/pages/dashboard/DashboardPage.tsx`
4. `frontend/src/pages/chat/ChatPage.tsx`
5. legacy API key 与旧 pin/exclude 兼容路径的退出条件文档

## 假设与非目标

- 保持 FastAPI 路径、请求/响应模型、SSE 事件顺序及 `backend/openapi.json` 不变。
- 保持前端文案、交互步骤、权限行为和视觉布局不变。
- 不在结构重构中删除 legacy API key、旧数据兼容字段或数据库迁移逻辑。
- 不同时引入新功能、依赖升级、数据库变更或性能优化。
- 每个任务独立提交；提交说明使用中文。

## 当前问题与目标边界

### 后端

当前 `documents.py` 同时承担 HTTP 映射、来源识别、推荐问题组装、任务入队、审计元数据构造和任务 SSE 轮询。目标结构增加一个边界明确的应用服务层；只有依赖 SSE/FastAPI 协议类型的适配器保留在 `api`：

```text
api/routes/documents.py
    ├── services/document_import_service.py  # 文件/URL 导入用例编排
    ├── services/document_operations.py      # demo 导入与来源删除
    ├── services/document_job_service.py     # 清空/重建任务契约
    ├── services/document_audit.py           # 审计元数据构造与记录入口
    └── api/document_job_stream.py            # 后台任务状态到 SSE 事件的协议适配
             │
             ├── jobs/
             ├── rag/
             └── persistence/
```

路由只保留：鉴权和依赖注入、FastAPI 参数解析、异常到 HTTP 状态映射、响应模型组装。

依赖规则为 `api → services → rag/jobs/persistence`；`services` 禁止依赖 FastAPI 请求/响应对象和 `api.models`。服务接口保持具体，不创建一个接收任意 `action/job_type/target_path` 的万能函数。

### 前端

当前 `DocumentPanel` 同时承担 API 调用、任务轮询、版本冲突状态、上传/拖拽状态、删除/清空动作和 JSX。目标结构为：

```text
components/sidebar/DocumentPanel.tsx       # 组合与展示
    ├── features/documents/hooks/useDocumentImport.ts
    ├── features/documents/hooks/useDocumentMutations.ts
    └── components/sidebar/document-panel/
            ├── DocumentImportControls.tsx
            └── DocumentImportFeedback.tsx
                         │
                         └── shared/api/
```

`DashboardPage` 和 `ChatPage` 采用相同原则：页面保留装配，数据派生进入 hook，重复或独立的展示区块进入命名组件。

## 成功标准

- 所有现有接口、OpenAPI 快照、SSE 事件与 UI 行为保持不变。
- `documents.py` 不再包含审计元数据构造、任务轮询循环、推荐问题收集或后台任务 target path 拼装。
- `DocumentPanel.tsx` 不再直接调用 `shared/api`，异步流程由 feature hooks 负责。
- `DashboardPage` 不在 render 主体中集中执行全部指标聚合。
- `ChatPage` 不再直接管理 localStorage 搜索偏好，桌面和移动端不重复实现策略选项。
- 行数只作为观察指标而非唯一目标：`documents.py` 约降到 250–300 行，`DocumentPanel.tsx` 约降到 180–240 行，`DashboardPage.tsx` 与 `ChatPage.tsx` 各降到约 250 行以内。
- `scripts/run-checks.sh`、相关 E2E 和结构守卫全部通过。

## 依赖顺序

```text
后端行为护栏
  → 审计拆分
  → SSE 任务流拆分
  → 导入编排拆分
  → 后端结构守卫

前端导入 hook
  → 删除/清空 hook
  → DocumentPanel 展示拆分
  → Dashboard/Chat 次级热点
  → 前端结构守卫

后端与前端主链可并行；同一条链内按顺序执行。
```

## 第一阶段：后端 Documents 路由瘦身（P0）

### Task 1：锁定 Documents 路由行为

**描述：** 在移动代码前补足针对内部职责的特征测试，锁定来源版本识别、URL 审计脱敏、任务 SSE 事件顺序及导入结果组装。测试 API 行为，不重新设计接口。

**验收标准：**

- 文件、URL、版本冲突、清空和重建索引路径均有行为断言。
- SSE 保持 `progress → done/error` 顺序及现有 payload 字段。
- `backend/openapi.json` 无变化。

**验证：**

- `cd backend && uv run pytest tests/test_document_job_routes.py tests/test_api_endpoints.py tests/test_workspace_scoped_kb_api.py -q`
- `cd backend && uv run pytest tests/test_openapi_snapshot.py -q`

**依赖：** 无

**可能涉及文件：**

- `backend/tests/test_document_job_routes.py`
- `backend/tests/test_document_services.py`（新增）

**规模：** S

### Task 2：抽取文档审计模块

**描述：** 将 URL 脱敏、来源审计身份和各类文档任务审计元数据移到 `services/document_audit.py`。模块接受明确参数和可注入的 `record_event`，不依赖 FastAPI 请求/响应对象。

**验收标准：**

- `documents.py` 不再包含 URL 脱敏和审计 metadata 拼装。
- 审计 action、actor、target、workspace 和脱敏结果与原实现一致。
- 现有路由测试的 patch 接缝通过依赖注入保持可用，避免一次修改大量测试。

**验证：**

- `cd backend && uv run pytest tests/test_document_services.py tests/test_document_job_routes.py -q`

**依赖：** Task 1

**可能涉及文件：**

- `backend/src/services/__init__.py`（新增）
- `backend/src/services/document_audit.py`（新增）
- `backend/src/api/routes/documents.py`
- `backend/tests/test_document_services.py`

**规模：** M

### Task 3：抽取后台任务 SSE 适配器

**描述：** 将任务轮询、progress/done payload 和 `EventSourceResponse` 创建逻辑移到 `document_job_stream.py`。该模块是协议适配层，可依赖 SSE 类型，但不负责入队和业务决策。

**验收标准：**

- `documents.py` 不再包含轮询 `asyncio` 循环和 SSE payload helper。
- 成功、失败、缺失任务及既有版本提示的事件行为不变。
- 轮询间隔以命名常量或构造参数表达，测试可注入任务读取函数。

**验证：**

- `cd backend && uv run pytest tests/test_document_services.py tests/test_document_job_routes.py -q`

**依赖：** Task 1

**可能涉及文件：**

- `backend/src/api/document_job_stream.py`（新增）
- `backend/src/api/routes/documents.py`
- `backend/tests/test_document_services.py`

**规模：** M

### Task 4A：抽取文件与 URL 导入编排服务

**描述：** 创建 `DocumentImportService`，集中来源存在性判断、默认版本策略、文件/URL 导入任务参数组装和入队。服务返回普通 dataclass/dict，不抛 `HTTPException`，由路由完成 HTTP 映射。

**验收标准：**

- 路由函数只包含参数处理、权限依赖、服务调用和响应映射。
- 服务不依赖 `Request`、`Response`、`HTTPException` 或 `EventSourceResponse`。
- 文件与 URL 的版本判断共享同一个明确的来源策略，避免两套近似分支继续漂移。
- 临时上传文件的所有权和异常清理责任由接口文档及测试明确锁定。

**验证：**

- `cd backend && uv run pytest tests/test_document_services.py tests/test_document_job_routes.py tests/test_api_routes_coverage.py tests/test_workspace_scoped_kb_api.py -q`
- `cd backend && uv run pytest tests/test_openapi_snapshot.py -q`

**依赖：** Tasks 2、3

**可能涉及文件：**

- `backend/src/services/document_import_service.py`（新增）
- `backend/src/api/routes/documents.py`
- `backend/tests/test_document_services.py`
- `backend/tests/test_document_job_routes.py`

**规模：** M

### Task 4B：抽取同步文档操作

**描述：** 将 demo 文档导入、推荐问题素材收集和来源删除结果移到 `document_operations.py`。服务返回普通结果对象；路由继续负责 404 与 Pydantic 响应映射。

**验收标准：**

- demo 导入消息、chunk 数、来源列表和推荐问题与当前一致。
- 删除不存在来源仍由路由映射为 404，成功删除的审计字段不变。
- 推荐问题收集不再出现在路由文件中。

**验证：**

- `cd backend && uv run pytest tests/test_document_services.py tests/test_workspace_rbac_routes.py tests/test_workspace_scoped_kb_api.py -q`

**依赖：** Task 2

**可能涉及文件：**

- `backend/src/services/document_operations.py`（新增）
- `backend/src/services/document_audit.py`
- `backend/src/api/routes/documents.py`
- `backend/tests/test_document_services.py`

**规模：** M

### Task 4C：抽取清空与重建任务契约

**描述：** 将清空工作区和重建索引的 job type、target path、参数及审计调用移到 `document_job_service.py`，以两个具体函数暴露，不允许路由自行拼任务契约。

**验收标准：**

- `documents.py` 不再出现清空/重建任务的 target path 字符串。
- 清空和重建的 workspace、actor、job type 与审计行为不变。
- 两个操作不能通过任意 action 参数互相冒充。

**验证：**

- `cd backend && uv run pytest tests/test_document_services.py tests/test_document_job_routes.py tests/test_jobs_routes.py -q`

**依赖：** Task 2

**可能涉及文件：**

- `backend/src/services/document_job_service.py`（新增）
- `backend/src/api/routes/documents.py`
- `backend/tests/test_document_services.py`

**规模：** M

### Task 5：固化后端结构边界

**描述：** 更新结构守卫和架构文档，明确 Documents 路由的允许职责，并阻止审计构造、任务轮询和导入编排重新堆回路由。

**验收标准：**

- 结构守卫能检测 `documents.py` 重新直接实现任务轮询或审计元数据构造的回退。
- 后端架构文档列出应用服务层与 SSE 协议适配器的依赖方向。
- `CLAUDE.md` 中过时的路由数量/行数描述与真实结构一致。

**验证：**

- `python scripts/check-structure.py`
- `bash scripts/run-checks.sh`

**依赖：** Tasks 4A、4B、4C

**可能涉及文件：**

- `scripts/check-structure.py`
- `docs/architecture/backend-structure.md`
- `docs/architecture/dependency-rules.md`
- `CLAUDE.md`

**规模：** M

### Checkpoint A：后端完成

- 全量后端 pytest 通过。
- OpenAPI 快照和前端生成类型无差异。
- `documents.py` 只保留 HTTP/鉴权/响应映射职责，不直接拼后台任务契约。
- 单独进行一次代码审查后再进入前端拆分。

## 第二阶段：DocumentPanel 交互与展示分离（P0）

### Task 6：抽取文档导入 hook

**描述：** 将文件上传、URL 导入、demo 导入、版本冲突处理、任务轮询、进度和导入后引导状态移到 `useDocumentImport`。hook 通过参数接收 workspace 和刷新回调。

**验收标准：**

- 文件、URL、demo 和 replace/append/skip 流程均由 hook 暴露的动作驱动。
- API 调用顺序、toast 条件、进度状态和推荐问题保持不变。
- hook 不返回 JSX，只返回明确的状态和动作对象。

**验证：**

- `cd frontend && npx vitest src/test/__tests__/hooks/useDocumentImport.test.ts src/test/__tests__/components/DocumentPanel.test.tsx src/test/__tests__/components/SidebarInteraction.test.tsx`

**依赖：** 无；可与后端 Task 1–5 并行

**可能涉及文件：**

- `frontend/src/features/documents/hooks/useDocumentImport.ts`（新增）
- `frontend/src/test/__tests__/hooks/useDocumentImport.test.ts`（新增）
- `frontend/src/components/sidebar/DocumentPanel.tsx`

**规模：** M

### Task 7：抽取删除与清空 hook

**描述：** 将删除来源、清空知识库、确认框目标状态和完成后刷新逻辑移到 `useDocumentMutations`，使 `DocumentPanel` 不再直接依赖 `shared/api`。

**验收标准：**

- `DocumentPanel.tsx` 中不存在直接 `api.*` 调用。
- 删除和清空的权限、确认、toast、刷新及后台任务等待行为不变。
- import hook 与 mutation hook 不共享隐式模块状态。

**验证：**

- `cd frontend && npx vitest src/test/__tests__/hooks/useDocumentMutations.test.ts src/test/__tests__/components/DocumentPanel.test.tsx src/test/__tests__/components/SidebarInteraction.test.tsx`

**依赖：** Task 6

**可能涉及文件：**

- `frontend/src/features/documents/hooks/useDocumentMutations.ts`（新增）
- `frontend/src/test/__tests__/hooks/useDocumentMutations.test.ts`（新增）
- `frontend/src/components/sidebar/DocumentPanel.tsx`

**规模：** M

### Task 8：拆分 DocumentPanel 展示区块

**描述：** 将上传/拖拽/URL 控件和进度/版本冲突/导入后引导拆成两个纯展示组件。`DocumentPanel` 负责组合来源列表、两个 hooks 与展示组件，不新增全局 context。

**验收标准：**

- 子组件只接收 props，不调用 API、不访问 workspace 全局状态。
- 键盘 Enter、拖拽深度、文件 input reset 和版本操作仍有测试覆盖。
- `DocumentPanel` 主体能在一个屏幕内读懂其组合关系，避免继续拆成过多微组件。

**验证：**

- `cd frontend && npx vitest src/test/__tests__/components/DocumentPanel.test.tsx src/test/__tests__/components/SidebarInteraction.test.tsx`
- `cd frontend && npm run build`

**依赖：** Tasks 6、7

**可能涉及文件：**

- `frontend/src/components/sidebar/document-panel/DocumentImportControls.tsx`（新增）
- `frontend/src/components/sidebar/document-panel/DocumentImportFeedback.tsx`（新增）
- `frontend/src/components/sidebar/DocumentPanel.tsx`
- `frontend/src/test/__tests__/components/DocumentPanel.test.tsx`

**规模：** M

### Checkpoint B：DocumentPanel 完成

- 前端全量 Vitest 与生产构建通过。
- `DocumentPanel` 不直接访问 API，展示组件无业务副作用。
- 手工验证文件上传、URL 导入、版本冲突、删除和清空流程。
- 运行 `frontend/e2e/editor-jobs.spec.ts`。

## 第三阶段：页面级次级热点（P1）

### Task 9：抽取 Dashboard 数据 hook 与纯指标模型

**描述：** 将日志加载、时间范围和错误状态移到 `useDashboardData`，将统计卡、小时分布、质量分布、Token 与费用计算移到纯函数 `dashboardMetrics.ts`。页面只消费已命名的 view model。

**验收标准：**

- 相同日志输入产生与当前一致的统计值、小时分布和质量分布。
- 时间范围变化仍触发重新请求，失败和空数据状态不变。
- 纯函数允许注入 `now`，保留旧数组响应与 `QueryLogsResponse` 两种输入，并独立测试后端总费用优先级。

**验证：**

- `cd frontend && npx vitest src/test/__tests__/features/dashboard/dashboardMetrics.test.ts src/test/__tests__/components/DashboardPage.test.tsx src/test/__tests__/components/DashboardPageInteraction.test.tsx`

**依赖：** Checkpoint B 后执行

**可能涉及文件：**

- `frontend/src/features/dashboard/hooks/useDashboardData.ts`（新增）
- `frontend/src/features/dashboard/model/dashboardMetrics.ts`（新增）
- `frontend/src/test/__tests__/features/dashboard/dashboardMetrics.test.ts`（新增）
- `frontend/src/pages/dashboard/DashboardPage.tsx`

**规模：** M

### Task 10：拆分 Dashboard 独立展示区块

**描述：** 抽取图表区域和查询日志表格，页面保留标题、筛选、状态分支和区块装配。不要为单个 `StatCard` 再建立复杂抽象层。

**验收标准：**

- 图表和表格组件为纯展示组件，数据均由 props 输入。
- 展开全部日志、错误标记和格式化结果与原实现一致。
- 页面布局和响应式 class 不变。

**验证：**

- `cd frontend && npx vitest src/test/__tests__/components/DashboardPage.test.tsx src/test/__tests__/components/DashboardPageInteraction.test.tsx`
- `cd frontend && npm run build`

**依赖：** Task 9

**可能涉及文件：**

- `frontend/src/components/dashboard/DashboardCharts.tsx`（新增）
- `frontend/src/components/dashboard/QueryLogTable.tsx`（新增）
- `frontend/src/pages/dashboard/DashboardPage.tsx`
- `frontend/src/test/__tests__/components/DashboardPage.test.tsx`

**规模：** M

### Task 11：统一 Chat 搜索偏好状态与控件

**描述：** 把 localStorage 初始化/持久化移到 `useSearchPreferences`，并让桌面与移动端复用同一策略选项组件。使用显式 `variant` 而非多个布尔参数表达布局差异。

**验收标准：**

- `ChatPage` 不直接读写 `kb_web_search` 和 `kb_search_strategy`。
- 桌面和移动端使用同一组选项定义、键盘导航和 ARIA 语义。
- 消息发送仍使用当前 web search 与 strategy 值。

**验证：**

- `cd frontend && npx vitest src/test/__tests__/hooks/useChatSearchPreferences.test.ts src/test/__tests__/components/ChatArea.test.tsx src/test/__tests__/components/ChatAreaInteraction.test.tsx`
- `cd frontend && npm run build`

**依赖：** Checkpoint B 后执行；可与 Tasks 9–10 并行

**可能涉及文件：**

- `frontend/src/features/chat/hooks/useSearchPreferences.ts`（新增）
- `frontend/src/components/chat/SearchPreferencesPanel.tsx`（新增）
- `frontend/src/pages/chat/ChatPage.tsx`
- `frontend/src/test/__tests__/hooks/useChatSearchPreferences.test.ts`（新增）

**规模：** M

### Task 11B：拆分 Chat 输入与消息区域

**描述：** 将输入草稿、Enter/Shift+Enter、自动高度、发送/停止和聚焦行为移到 `useChatComposer`/`ChatComposer`，将加载骨架、空状态、消息列表和自动滚动移到 `ChatMessageList`。页面保留导航和应用级装配。

**验收标准：**

- Enter 发送、Shift+Enter 换行、streaming 禁用与停止按钮行为不变。
- 消息加载完成后的二次滚动、空状态主操作和引用点击行为保持一致。
- 展示组件不读写 localStorage，也不直接决定搜索策略。

**验证：**

- `cd frontend && npx vitest src/test/__tests__/components/ChatArea.test.tsx src/test/__tests__/components/ChatAreaInteraction.test.tsx`
- `cd frontend && npm run build`

**依赖：** Task 11

**可能涉及文件：**

- `frontend/src/features/chat/hooks/useChatComposer.ts`（新增）
- `frontend/src/components/chat/ChatComposer.tsx`（新增）
- `frontend/src/components/chat/ChatMessageList.tsx`（新增）
- `frontend/src/pages/chat/ChatPage.tsx`
- `frontend/src/test/__tests__/components/ChatAreaInteraction.test.tsx`

**规模：** M

### Task 12：固化前端边界并同步文档

**描述：** 更新结构守卫和前端架构文档，防止 `DocumentPanel` 重新直接依赖 API，以及 Chat 页面重新内联 localStorage 偏好逻辑。

**验收标准：**

- 结构守卫能发现上述两个明确回退模式。
- 文档准确说明 documents hooks、Dashboard hook 和 Chat 偏好模块的位置。
- 不建立泛化的“所有组件都不能访问 API”规则，以免误伤现有合法结构。

**验证：**

- `python scripts/check-structure.py`
- `bash scripts/run-checks.sh`

**依赖：** Tasks 8–11B

**可能涉及文件：**

- `scripts/check-structure.py`
- `docs/architecture/frontend-structure.md`
- `docs/architecture/dependency-rules.md`
- `CLAUDE.md`

**规模：** M

### Checkpoint C：结构优化完成

- `bash scripts/run-checks.sh` 全部通过。
- `cd frontend && npx playwright test e2e/editor-jobs.spec.ts e2e/auth-rbac.spec.ts` 通过。
- OpenAPI 快照和生成类型无漂移。
- 对四个热点文件做前后职责对比，确认减少的是概念数量，而不只是移动行数。
- 进行独立代码审查，确认没有无关格式化或功能改动混入。

## 第四阶段：兼容债务治理（P2，独立决策，不与重构混合）

### Task 13：建立兼容路径退出清单

**描述：** 记录 legacy API key、旧 debug pin/exclude 字段和旧 Chroma metadata 的调用方、生产使用条件、移除前置条件及目标版本。此任务只形成决策记录，不删除兼容代码。

**验收标准：**

- 每条兼容路径都有 owner、使用证据、移除条件和迁移/回滚方式。
- 明确哪些兼容仅限本地开发，哪些仍涉及历史数据。
- 后续删除工作单独立项，不与本轮结构重构混合。

**验证：**

- 人工审阅兼容清单与现有测试引用是否对应。

**依赖：** Checkpoint C 后执行

**可能涉及文件：**

- `docs/architecture/legacy-compatibility.md`（新增）

**规模：** S

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 后端测试大量 patch 路由模块内部符号 | 中 | 新模块依赖通过路由注入，先保持原 patch 接缝；稳定后再单独迁移测试 |
| SSE 拆分改变事件顺序或 fallback payload | 高 | Task 1 先锁定事件序列和字段，Task 3 使用可注入 job reader 做确定性测试 |
| hook 抽取造成闭包状态过期或重复刷新 | 高 | 对 workspace 切换、轮询进度、成功 toast 条件和 unmount 行为做 hook 测试 |
| 为减少行数制造过多小文件 | 中 | 只抽取有独立职责、独立状态或可命名输入输出的模块；纯一行 wrapper 不保留 |
| 重构与功能改动混在一起 | 高 | 每个任务独立提交；重构期间冻结相关功能修改或先 rebase 后再继续 |
| 架构文档再次失真 | 中 | 最后一项任务同步结构守卫与文档，CI 中继续执行 `check-structure.py` |

## 预计投入

- P0 后端 Documents：约 1.5–2 个工程日，4–5 个独立提交。
- P0 前端 DocumentPanel：约 1–1.5 个工程日，3 个独立提交。
- P1 Dashboard 与 Chat：约 1–2 个工程日，3–4 个独立提交。
- P2 兼容治理文档：约 0.5 个工程日。
- 总计约 4–6 个工程日；若由自动化代理实施，建议按任务逐个执行并在每个 Checkpoint 暂停审查。

## 推荐执行范围

第一轮建议只批准 Tasks 1–8。它们解决最明确的两个结构热点，收益高且行为边界已有充分测试。Tasks 9–13 在 Checkpoint B 后根据文件增长速度和团队近期需求决定是否继续，避免为了“看起来整齐”进行无收益拆分。
