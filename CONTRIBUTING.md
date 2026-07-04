# Contributing

本仓库后端使用 `uv` 管理 Python 依赖，前端使用 `npm`。提交前请保持改动范围清晰，并在行为、接口、测试流程、契约或启动方式变化时同步更新文档。

## 开发环境

### 前置要求

- Python 3.11+（推荐 3.12，GitHub CI 也使用 3.12）
- Node.js 20+
- `uv`

### 初始化

```bash
git clone <repo-url>
cd KnowBase

cp backend/.env.example backend/.env

cd backend
uv sync

cd ../frontend
npm install
```

Windows PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env
```

## 本地运行

优先使用仓库根目录下的辅助脚本：

```bash
bash scripts/dev.sh
```

Windows PowerShell:

```powershell
scripts\dev.bat
```

也可以分别启动：

```bash
cd backend
uv run uvicorn src.api.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

Docker 开发环境：

```bash
docker compose up --build
```

或：

```bash
bash scripts/dev.sh --docker
```

## 测试要求

至少运行覆盖你改动范围的测试。涉及接口、OpenAPI、类型生成、启动方式或跨平台兼容时，建议跑完整矩阵。

### 后端

```bash
cd backend
uv run pytest tests --tb=short -q
```

### 前端

```bash
cd frontend
npm test
```

### 构建检查

```bash
cd frontend
npm run build
```

类型检查（`tsc -b`）和 Vite 打包一并执行。这是提交前应完成的本地检查；当前 CI 默认执行前端单测，不替代构建自检。

### 前端 API 类型漂移检查

```bash
cd frontend
npm run check-api-types
```

这条命令会重新生成 `src/lib/api-types.openapi.ts`，并在生成物与提交态不一致时失败。

## 协作规则

- 后端接口变化后，要先导出 `backend/openapi.json`，再同步更新前端生成的 API 类型。
- 启动方式、配置项、产品行为、工作区语义或架构假设变化后，要同步更新 `README.md`、`CLAUDE.md`、`docs/requirements.md` 或相关文档。
- 新增配置项已经体现在 `backend/.env.example`。
- 不要提交密钥、本地数据库、覆盖率产物（如 `backend/.coverage`）或运行期生成文件。
- 尽量保持 PR 小而明确，一个 PR 解决一个清晰问题。
- 跨平台测试不要写死 Windows 或 POSIX 路径分隔符，优先用 `pathlib.Path`、`os.path` 或前端等价方式构造路径断言。
- 不要把当前工作区能力写成“多租户安全隔离”；它目前只是应用层作用域。

## 契约与类型更新

如果 FastAPI 路由或 Pydantic schema 发生变化，按这个顺序更新：

```bash
cd backend
uv run python scripts/export_openapi.py
```

```bash
cd frontend
npm run gen-api-types
```

其中：

- `backend/openapi.json` 是提交态 API 快照
- `frontend/src/lib/api-types.openapi.ts` 是生成物
- `frontend/src/lib/api-types.ts` 中的 SSE 手写类型由后端测试校验同步
- 后端唯一 Python 应用根是 `backend/`；不要在仓库根目录执行 `uv sync` 或把根目录当作 Python 项目根

同时确认这些文件已同步：

- `backend/openapi.json`
- `frontend/src/lib/api-types.openapi.ts`
- 任何依赖这些类型的测试或消费代码

## 模块拆分约定

保持模块职责单一。以下模式在项目中已有实践：

- **后端** — 当 `chat_stream_service.py` 中的辅助逻辑（调试累加、持久化）膨胀到可独立测试的规模时，拆至 `chat_debug.py` 和 `chat_persistence.py`，保持主类 ~200 行
- **前端** — 当 hook 的多个状态维度（消息列表 + 来源固定 + 类型定义）耦合在一起时，拆至 `hooks/chat/` 子目录下的独立文件
- **组件** — 单体组件超过 200 行时考虑拆为多个子组件（参考 `components/browser/` 和 `components/sidebar/`）

## 提交前检查

- 改动目标和原因清晰。
- 后端 + 前端测试已在本地通过。
- `npm run build` 无报错。
- 如果接口或 OpenAPI 变更，`scripts/export_openapi.py` 与 `npm run gen-api-types` 已执行并提交生成物。
- `npm run check-api-types` 通过。
- 如果接口、行为、工作区语义或配置变更，文档已同步更新。
