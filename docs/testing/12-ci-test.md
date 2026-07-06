# CI 测试文档

## 1. 概述

KnowBase 当前使用 GitHub Actions 作为默认 CI。目标不是只“跑得通测试”，而是阻止以下几类常见回归进入 `main`：

- 后端行为回归
- 前端行为回归
- 前端构建失败
- 后端 OpenAPI 快照与前端生成类型漂移

## 2. 当前 Workflow

实际 workflow 文件为 `.github/workflows/ci.yml`，当前包含三个 job：

### Backend

- 安装 Python 3.12 与 `uv`
- 在 `backend/` 工作目录执行 `uv sync`
- 运行 `uv run pytest tests --tb=short -q`

### Frontend

- 安装 Node.js 20
- 在 `frontend/` 执行 `npm ci`
- 运行 `npm test`
- 运行 `npm run build`
- 运行 `npm run check-api-types`

### Playwright E2E

- 安装 Python 3.12、`uv` 与 Node.js 20
- 执行 `backend/uv sync` 与 `frontend/npm ci`
- 安装 Chromium 浏览器 `npx playwright install --with-deps chromium`
- 运行 `cd frontend && npm run e2e`

## 3. 质量门禁

以下检查默认阻断合并：

- 后端 pytest 失败
- 前端 vitest 失败
- 前端 TypeScript / Vite 构建失败
- `npm run check-api-types` 发现生成类型未同步
- Playwright 认证 / 权限关键路径失败

其中 `npm run check-api-types` 的行为是：

1. 重新读取 `backend/openapi.json`
2. 生成 `frontend/src/shared/api/api-types.openapi.ts`
3. 对生成物执行 `git diff --exit-code`

如果接口变了但生成物没提交，CI 会失败。

## 4. 契约同步约定

当前仓库的 API 契约链路是：

1. FastAPI 应用
2. `backend/openapi.json`
3. `frontend/src/shared/api/api-types.openapi.ts`
4. `frontend/src/shared/api/index.ts` 与消费代码

后端测试还会校验 `backend/openapi.json` 是否与当前 FastAPI schema 一致，因此快照陈旧同样会阻断提交。

## 5. 本地模拟 CI

提交前建议按下面顺序执行：

```bash
bash scripts/run-checks.sh
```

或按分步方式执行：

```bash
cd backend && uv run pytest tests --tb=short -q
cd frontend && npm test
cd frontend && npm run build
cd frontend && npm run check-api-types
cd frontend && npm run e2e
```

如果后端接口发生变化，再补：

```bash
cd backend && uv run python scripts/export_openapi.py
cd frontend && npm run gen-api-types
```

## 6. 维护要求

- 本文档必须与 `.github/workflows/ci.yml` 保持一致
- 若 CI 新增或移除门禁，要同步更新本文档、`README.md` 与 `CONTRIBUTING.md`
- 不要在文档里保留已经下线的 CI 命令或旧测试发现方式
