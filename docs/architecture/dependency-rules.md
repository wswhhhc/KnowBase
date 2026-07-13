# 依赖方向规则

KnowBase 当前仓库的默认依赖方向如下：

## 后端

- `api/` 只处理 HTTP 协议、鉴权、参数校验和响应映射
- `services/` 负责需要协调 `rag`、`jobs`、`persistence` 的应用用例；服务只返回普通 Python 数据，不依赖 FastAPI 请求/响应对象或 `api.models`
- `graph/` 与 `rag/` 负责核心问答与知识库逻辑，不反向依赖 `api.models`
- `persistence/` 负责 Postgres/SQLite repository、SQLAlchemy session 和业务持久化细节，路由与服务直接依赖 repository / persistence helpers
- `jobs/` 负责 RQ 入队、worker 执行和任务状态更新，不承载 HTTP 请求/响应对象
- `config/` 下按职责分为 typed settings、runtime overrides、public settings 和 constants 访问入口

允许：

- `api -> graph`
- `api -> rag`
- `api -> persistence facade`
- `api -> jobs`
- `api -> services`
- `services -> rag`
- `services -> jobs`
- `services -> persistence`
- `jobs -> rag`
- `jobs -> persistence`
- `graph -> rag`
- `graph -> config`
- `rag -> config`

禁止：

- `rag -> api.models`
- `graph -> React` 或任何前端概念
- 核心逻辑直接依赖 FastAPI 请求/响应对象
- `services -> api.models` 或 FastAPI 请求/响应对象

## 前端

- `app/` 只负责应用装配、导航和入口
- `pages/` 负责页面级容器
- `features/` 放交互与状态逻辑
- `shared/api/` 放 API client、SSE、错误处理和契约类型
- 组件不得再从根 `App.tsx` 反向导入 `ViewType`

允许：

- `app -> pages`
- `pages -> features`
- `pages -> shared`
- `features -> shared`

禁止：

- 页面组件和 Sidebar 从根 `App.tsx` 反向拿类型
- 所有 API 逻辑重新堆回单个 `lib/api.ts`
- `components/sidebar/DocumentPanel.tsx` 直接调用 `shared/api/` 的运行时 client；文档交互应经由 `features/documents/hooks/`
- `pages/chat/ChatPage.tsx` 直接读写 `kb_web_search` 或 `kb_search_strategy`；偏好应经由 `features/chat/hooks/useSearchPreferences.ts`

## 数据与样例

- `examples/` 只放版本化样例
- `runtime/` 只放运行期数据
- `backend/.env` 中的相对路径以仓库根为基准，默认落到 `runtime/local/`
