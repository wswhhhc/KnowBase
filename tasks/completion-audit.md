# Tasks 1–13 完成性证据

本文件按 `tasks/plan.md` 的验收标准逐项记录直接证据，不以 `tasks/todo.md` 的勾选状态代替验证。最终结论还需同时满足仓库全量门禁、关键 E2E、独立五轴代码审查和 GitHub CI。

| 项目 | 实现证据 | 行为/边界证据 | 当前判定 |
|---|---|---|---|
| Task 1 Documents 行为锁定 | `backend/src/api/routes/documents.py`、`backend/src/api/document_job_stream.py` | `test_document_job_routes.py` 覆盖文件、URL、版本冲突、清空、重建；`test_document_services.py` 覆盖 `progress → done/error`、失败、取消、缺失任务；`test_openapi_snapshot.py` 锁定 OpenAPI | 已证明 |
| Task 2 文档审计模块 | `backend/src/services/document_audit.py` 集中来源身份、URL 脱敏和审计 metadata | `test_document_services.py` 与 `test_document_job_routes.py` 断言 action、actor、target、workspace 与脱敏结果 | 已证明 |
| Task 3 后台任务 SSE 适配器 | `backend/src/api/document_job_stream.py` 独占 `EventSourceResponse`、轮询、payload 与即时 done；Documents 路由不再内联 SSE generator | 可注入 `get_job`/`poll_seconds` 的确定性测试覆盖 fallback、去重、成功、失败、取消、缺失和既有版本提示 | 已证明 |
| Task 4A 文件/URL 导入编排 | `backend/src/services/document_import_service.py` 共享来源策略与固定入队参数，返回普通 dataclass | ownership 测试锁定 probe/校验/入队失败由路由清理、入队成功后转交 worker；`backend-structure.md` 记录 transfer point 和取消/worker 清理责任 | 已证明 |
| Task 4B 同步文档操作 | `backend/src/services/document_operations.py` 承担 demo、推荐问题和删除结果 | service/路由测试锁定 demo 结果、推荐问题、删除 404 与审计字段 | 已证明 |
| Task 4C 清空/重建任务契约 | `backend/src/services/document_job_service.py` 以两个具体函数固定 job type、target path、参数和审计 | `test_document_services.py`、`test_document_job_routes.py`、`test_jobs_routes.py` 精确断言两个任务契约不能互相冒充 | 已证明 |
| Task 5 后端结构边界 | `scripts/check-structure.py` 禁止 Documents 路由直接轮询、审计拼装、target path、推荐问题、入队、任务读取和 SSE 响应；禁止 services 依赖 FastAPI/api models/SSE 类型 | `test_structure_guard.py` 含正例、精确性与当前仓库检查；`backend-structure.md`、`dependency-rules.md`、`CLAUDE.md` 已同步 | 已证明 |
| Task 6 文档导入 hook | `frontend/src/features/documents/hooks/useDocumentImport.ts` 暴露 file/URL/demo/replace/append/skip、进度和引导状态，不返回 JSX | hook 与组件测试覆盖调用顺序、toast 条件、进度回调、推荐问题、URL Enter、append/skip/demo | 已证明 |
| Task 7 删除/清空 hook | `useDocumentMutations.ts` 持有删除目标、清空确认状态、删除/清空副作用和刷新；`DocumentPanel` 无运行时 API 调用 | hook/Panel/Sidebar 测试覆盖确认状态、权限、toast、refresh、错误和后台任务等待 | 已证明 |
| Task 8 DocumentPanel 展示拆分 | `DocumentImportControls.tsx` 与 `DocumentImportFeedback.tsx` 仅接收 props；`DocumentPanel` 装配两个 hooks、展示组件、来源列表和确认框 | 测试覆盖 URL Enter、嵌套拖拽深度、file input reset、replace/append/skip；源码审查确认子组件无 API 调用和全局 workspace 访问 | 已证明 |
| Task 9 Dashboard 数据与指标 | `useDashboardData.ts` 管理请求、时间范围与 loading，并保持既有失败行为；`dashboardMetrics.ts` 纯计算并允许注入 `now` | metrics/page 测试覆盖旧数组与新响应、总费用优先级、时间范围、失败/空数据和统计分布 | 已证明 |
| Task 10 Dashboard 展示区块 | `DashboardCharts.tsx`、`QueryLogTable.tsx` 仅通过 props 接收数据，页面保留装配 | 页面测试覆盖超过 15 条的展开/收起、失败标记、Web 搜索、耗时/检索/Token/费用格式 | 已证明 |
| Task 11 Chat 搜索偏好 | `useSearchPreferences.ts` 独占 localStorage；`SearchPreferencesPanel.tsx` 的 desktop/mobile 复用 `SearchStrategyOptions` | 两端均为 radiogroup/radio、roving tabindex 和方向/Home/End 导航；发送参数与持久化测试通过 | 已证明 |
| Task 11B Chat 输入与消息区 | `useChatComposer.ts`、`ChatComposer.tsx`、`ChatMessageList.tsx` 分担输入状态、展示、空状态和滚动 | 测试覆盖 Enter、真实 Shift+Enter 换行、streaming/停止、空状态主操作、citation 传递和加载结束后的 deferred second scroll | 已证明 |
| Task 12 前端边界与文档 | 守卫只针对 `DocumentPanel` runtime API import 与 `ChatPage` 偏好 localStorage 回退；前端结构文档同步 hooks/展示边界 | 测试覆盖 barrel/subpath、named/default、type-only import 和变量化偏好键；当前仓库结构脚本通过 | 已证明 |
| Task 13 兼容退出清单 | `docs/architecture/legacy-compatibility.md` 记录 Legacy API Key、debug pin/exclude、Chroma metadata | 每项包含 owner、直接/间接使用证据、生产条件、移除门槛、迁移/回滚和不早于 v2.0.0；本轮未删除兼容实现 | 已证明 |

## Checkpoint 状态

| Checkpoint | 需要的最终证据 | 状态 |
|---|---|---|
| A 后端完成 | 后端全量 pytest、OpenAPI、结构守卫 | 714 通过/1 跳过，OpenAPI 类型同步与结构守卫通过 |
| B DocumentPanel 完成 | 前端全量 Vitest、构建、editor-jobs E2E、关键导入流程验证 | 312 项 Vitest、生产构建和 editor-jobs E2E 通过 |
| C 结构优化完成 | 仓库全量门禁、关键 E2E、四个热点职责对比、独立审查 | 全量门禁与 6 项关键 E2E 通过；四热点职责对比完成；独立五轴审查 Approve |

## 四个热点职责前后对比

| 热点 | 优化前需要同时理解的概念 | 优化后保留职责 | 被移出的独立职责 |
|---|---|---|---|
| `backend/src/api/routes/documents.py` | HTTP、权限、来源判断、审计 metadata、任务契约、SSE 轮询/payload、同步文档操作、临时文件清理 | HTTP 参数/权限、服务调用、响应与错误映射、入队前文件所有权 | 审计、导入编排、同步操作、维护任务契约和 SSE 协议适配分别进入命名模块 |
| `frontend/src/components/sidebar/DocumentPanel.tsx` | API 副作用、导入状态、删除/清空状态、拖拽/URL、进度、版本提示、来源列表和确认框 | 两个 hooks 与 Controls/Feedback/SourceList/ConfirmDialog 的页面级装配 | 导入副作用、mutation 状态、控件交互和反馈展示各自有单一 owner |
| `frontend/src/pages/dashboard/DashboardPage.tsx` | 请求、时间范围、loading/失败、统计归约、图表数据、日志表格式与展开状态 | 页面标题、筛选、状态分支与展示区块装配 | 请求进入 hook，指标进入纯模型，图表和日志表进入 props-only 组件 |
| `frontend/src/pages/chat/ChatPage.tsx` | localStorage 偏好、策略控件、输入草稿/键盘、消息空状态/滚动、导航和发送接线 | 导航、工作区与聊天应用级接线 | 偏好、策略选项、composer 状态/展示、消息列表/滚动各自进入命名 hook 或组件 |

独立五轴代码审查结论：**Approve**；无 Critical/Required，无 Security/Performance 阻断项。Optional 风险已记录在 `findings.md`，不改变本轮完成判定。
