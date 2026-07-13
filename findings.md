# 发现与决策

## 需求

- 延续 `tasks/plan.md` 中的 Tasks 9–13。
- 本轮优先文档同步、机械拆文件和小范围命名统一；不得改变功能、接口、文案或权限行为。
- 本轮追加完成性审计：查漏补缺 SSE 拆分、架构边界、最终代码审查，并证明计划内全部方案真实完成。

## 研究发现

- Tasks 1–8 已在 `main` 完成；后续未完成项为 Dashboard、Chat、前端边界与兼容债务治理。
- Task 9 要求将 Dashboard 的数据加载与指标派生移至 `features/dashboard/`，并允许纯指标函数注入当前时间。
- 结构守卫目前覆盖 Documents 路由和旧 API 路径，尚未覆盖 Dashboard 与 Chat 的新边界；该守卫将在 Task 12 更新。
- `DashboardPage.tsx` 当前同时包含请求、副作用状态、统计计算、小时桶计算和展示；其现有组件测试已覆盖总费用优先级、空状态与时间范围重取。
- `queryLogs(days, 1000)` 可能返回旧数组，也可能返回含 `logs` 与 `total_cost` 的响应对象；Task 9 的 hook 必须保留两种形状。
- Chat 页面直接管理 `kb_web_search`、`kb_search_strategy`，桌面与移动端共用策略常量但分别内联展示逻辑；现有交互测试覆盖持久化、键盘 radio 导航与发送参数。
- 当前 `tasks/todo.md` 的 Tasks 1–13 均已勾选，但通用完成门槛仍未勾选；`task_plan.md` 和 `progress.md` 的当前阶段/五问记录仍有旧阶段文字，需要在审计结束时校正。
- `main...HEAD` 当前包含 Tasks 9–13 的 10 个中文提交，工作区在审计开始时干净，diff 检查无空白错误；完成性仍需逐条验收证据和独立审查结果。
- 本轮采用增量交付、测试驱动、五轴审查与中文 Git 描述；先同步所有权/契约文档，再做保持行为不变的机械拆分和小范围改名，最后执行本地全量门禁与 GitHub CI。
- 文档同步只记录非显然的所有权、边界和退出条件，不新增复述代码的说明；CI 合并门槛为本地质量门禁、PR 必需检查和最终审查全部通过，禁止跳过失败检查。
- 独立终审初步确认两个 Required 候选：Task 11 的移动端搜索策略弹层缺少与桌面一致的 radio/ARIA/方向键语义和测试；Task 7 要求的删除目标与清空确认框状态仍留在 `DocumentPanel.tsx`，尚未归属 `useDocumentMutations`。
- 前端计划审计新增 Task 8 Required：`DocumentImportSection` 仍混合导入 controls 与进度/引导/版本提示 feedback，第二个拆出的是 source list，并未完成计划要求的 controls/feedback 两个纯展示组件。
- Task 8 存在可复现行为回退：`resetUploadState()` 移入 hook 后无法清空 DOM file input；上传完成后再次选择同一文件可能不触发 `change`。现有测试只覆盖拖拽，没有锁定 file input reset，需先补失败测试再修复。
- Task 8 的最小结构修复应是 `Controls + Feedback`：文件 input/ref 与拖拽可留在 Controls；进度、post-import guide、version prompt 仅通过显式状态/动作 props 进入 Feedback，避免再次搬运复杂度。
- 计划原文已直接证明 Task 7 的范围包含“确认框目标状态”，而现有 hook 只暴露 `deleteSource`/`clearKnowledgeBase`；Task 8 候选文件也明确为 `DocumentImportControls.tsx` 与 `DocumentImportFeedback.tsx`，不是当前单一 `DocumentImportSection.tsx`。
- `DocumentImportSection` 当前把 `fileInputRef`、拖拽深度、上传进度、post-import guide、版本冲突和 URL 控件集中在一个组件，符合“复杂度整体搬移”而非完成展示拆分的判定。
- 后端审计确认 Task 3 未完全拆出 SSE：`documents.py` 仍两处内联 `_probe_events` 并直接创建 `EventSourceResponse`；应由 `document_job_stream.py` 提供命名的即时 done 响应/事件适配器，路由只组装 fallback 数据。
- `job_event_source()` 的 missing、failed、canceled 与 progress 去重均缺直接回归测试；Task 3 至少明确要求成功、失败、缺失任务和既有版本提示行为不变。
- Task 4A 的临时上传文件所有权与异常清理缺少接口文档和直接断言：现有“删除”测试未断言文件不存在，也没有 enqueue 失败清理测试。
- Task 5 结构守卫没有禁止 Documents 路由直接调用 `enqueue_tracked_job`、`job_store.get_job`、`EventSourceResponse`，也未保护 services 层不依赖 FastAPI/api models；`CLAUDE.md` 还保留已漂移的文件行数说明。
- Task 12 现有守卫只匹配最窄字面量：无法拦截 `@/shared/api/*` 子模块导入，也无法拦截先把 localStorage 键赋给变量再访问的回退模式；测试同样只覆盖最窄样例。
- Task 13 的 Legacy API Key 调用方清单不完整，遗漏 bookmarks、chat、conversations、knowledge_base 等实际使用 `get_current_user_or_legacy_api_key` 的路由；前端文档还引用不存在的 `shared/api/api.ts`，测试数量也已漂移。
- 临时文件所有权转移点必须精确到“入队成功”：入队前冲突或异常由路由删除；入队成功后由 worker/取消路径负责。当前路由若在入队成功后的审计记录阶段抛错，通用 `except` 会误删已交给 worker 的文件，可能造成排队任务读不到文件。
- 前端 Task 8 的 file input 可在 `onChange` 捕获 `File` 后立即清空 `event.currentTarget.value`；版本冲突仍持有独立 `File` 对象，同时连续选择同一文件可再次触发事件。
- 前端 RED 已形成直接证据：mutation hook 新状态为 `undefined`、file input 仍是 `C:\\fakepath\\same.md`、移动弹层找不到 `radiogroup`；三项均为真实失败而非仅静态推断。
- Task 10 的 `QueryLogTable` 已实现 15 条截断、展开/收起、失败质量标记、Web 搜索图标与格式化列，但页面测试尚未覆盖这些分支；可用超过 15 条的日志夹具直接锁定。
- Task 11B 的 Shift+Enter、空状态主操作与加载结束后的二次滚动均在现有实现中，但缺直接测试；citation 的底层 `MessageBubble` 已有点击测试，仍需在装配层证明回调传递。
- 已补齐 Task 6/8 的 URL Enter、嵌套拖拽深度、append/skip、进度回调、demo、错误路径；Task 10 的展开/收起与失败格式；Task 11B 的 Shift+Enter、空状态主操作、citation 边界与加载结束二次滚动测试。
- 后端修复的 RED 证据同时暴露了两类真实所有权 bug：入队后 audit 异常误删 worker 文件，以及 ValueError 路径泄漏 route-owned 文件；两类均已由独立测试锁定并转绿。
- Legacy API Key 的直接后端调用方已用搜索确认：bookmarks、chat、conversations、jobs、knowledge_base、workspaces，此外 workspace/admin 依赖会把兼容认证传播到更多路由；清单必须按这一真实范围更新。
- `CLAUDE.md` 的固定测试数量与 `shared/api/api.ts` 路径均已过期；应改为稳定的测试命令/覆盖范围描述，并指向当前 `shared/api/` 分模块入口，避免再次漂移。
- 当前一键门禁实际执行 `uv run pytest tests`、结构守卫、前端 Vitest、生产构建和 API 类型漂移检查；`shared/api/` 当前由 `client.ts`、`sse.ts` 与领域模块组成，不存在统一 `api.ts`。
- 已建立 `tasks/completion-audit.md`，逐项把 Tasks 1–13 映射到实现、测试/守卫和当前判定；Checkpoint A/B/C 保持待最终全量重跑，避免提前宣告完成。
- 最终全量门禁在所有代码与守卫修改完成后通过：后端 714 通过/1 跳过、前端 32 文件/312 项、构建与 API 类型同步通过；inline type-only 允许/混合 runtime 拦截由 11 项守卫测试锁定。
- 独立最终五轴审查结论为 Approve：无 Critical/Required，无安全或性能阻断项；四个热点均减少了页面/路由必须同时持有的概念，而不是只移动行数。
- Optional 后续项：Dashboard 请求可增加 abort/序号防旧响应覆盖；搜索策略图标与模型可从 hook 移到 feature model；注入异常 audit recorder 时已入队任务仍会让 HTTP 返回 503。三项均为既有或非生产阻断行为，应另立任务。

## 技术决策

| 决策 | 理由 |
|------|------|
| Task 9 先于展示组件拆分 | 先稳定数据 view model，减少 Task 10 的 props 和重复计算 |
| 仅抽取现有逻辑 | 此阶段不引入新的指标、筛选策略或用户可见文案 |
| 将指标归约做成纯函数、请求状态做成 hook | 使统计值能用固定 `now` 测试，并让页面只负责装配 |
| Chat 偏好先抽取状态 hook，再迁移控件 | 可先以现有 localStorage 和发送参数测试保护行为，Task 11B 再处理编辑器与消息区 |
| Chat 拆分以页面保留应用接线、子组件接收显式 props 的方式完成 | 避免展示组件隐式读取偏好或控制导航；消息滚动和编辑器状态各归属对应模块 |
| 兼容路径仅记录退出门槛，不随本轮删除 | API Key 限本地开发；pin/exclude 与 Chroma 元数据均可能涉及历史数据，最早 v2.0.0 再单独处理 |
| 交付前独立审查 | 无 Critical/Required 发现；页面不再内联已抽取的状态与偏好逻辑，边界守卫、全量门禁和关键 E2E 均通过 |

## 遇到的问题

| 问题 | 解决方案 |
|------|---------|
| `tasks/todo.md` 的 Git 状态与内容 diff 不一致 | 不覆盖、不暂存；在提交前重新检查 |
| 直接执行 `npx vitest run` 目标测试超过 65 秒未返回 | 改用项目脚本的 Vitest 调用方式；先确认是否有残留进程或测试发现配置问题 |
| 指标测试将 UTC 小时写死为 `11`，与页面本地时区桶规则不一致 | 测试改为使用同一 `Date#getHours()` 规则推导预期，不修改生产逻辑 |
| 指标测试夹具未满足 OpenAPI 的数字字段和完整响应字段要求 | 将延迟空值表示为既有的 `0`，补齐 Token 汇总字段 |
| Dashboard 展示组件尚不存在 | 新增 `DashboardCharts` 和 `QueryLogTable`，避免为单个统计卡增加额外抽象 |
| Task 12 的首次盘点命令因 PowerShell 引号转义失败 | 拆分为独立文件读取和搜索命令；未改动仓库内容 |
| 从仓库根调用后端结构守卫测试，测试路径不存在 | 从 `backend/` 运行相同目标；守卫脚本本身已通过 |
| 阶段 6 持久计划补丁两次上下文不匹配 | 停止联动补丁，分别更新文件并按实际末行追加进度 |
| `using-agent-skills` 引用的 Definition of Done 路径不存在 | 使用 `rg` 定位真实引用文件；读取前不据此补写完成标准 |
| 技能目录中没有 `definition-of-done.md` 实体文件 | 按各已读取技能自身 Verification 清单和项目 `tasks/plan.md` 验收标准作为最终门禁，不虚构缺失引用内容 |
| 读取 Documents 前端文件时使用了不存在的旧目录 | 改用 `rg --files frontend/src` 定位当前目录结构后再读；Chat 文件路径已确认有效 |
