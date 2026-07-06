# E2E 测试文档

## 1. 当前状态

仓库现在已经接入 Playwright 基础设施，并落地了第一条真实可执行的 E2E 权限流：

- 未登录访问根页面时展示登录页
- `admin` 登录后可进入设置页并看到“用户管理 / 审计日志”
- `viewer` 登录后不会显示“设置 / 指标”导航
- `viewer` 直接请求 `/api/settings` 会收到 `403`
- `admin` 可创建用户、创建工作区并保存成员授权；新用户登录后只能看到被授权工作区
- `editor` 可导入示例资料、触发清空工作区后台任务，并在任务中心看到完成状态

当前测试文件：

- `frontend/e2e/auth-rbac.spec.ts`
- `frontend/e2e/editor-jobs.spec.ts`

## 2. 测试环境

Playwright 会自动启动两类本地服务，不需要手动先开前后端：

- 后端：`frontend/scripts/e2e/start-backend.mjs`
- 前端：`frontend/scripts/e2e/start-frontend.mjs`

后端启动前会执行：

- `backend/scripts/prepare_e2e_env.py`

这个脚本会重置 `runtime/e2e/`，初始化 SQLite E2E 数据库，并种入：

- `admin / admin-pass`
- `editor / editor-pass`
- `viewer / viewer-pass`

其中 `editor` 和 `viewer` 会被授予默认工作区成员关系。Playwright backend 启动脚本还会在本地拉起 fake Redis TCP 服务和真实 RQ worker，因此后台任务流可以在不依赖系统 Redis 的情况下进入 E2E。

## 3. 执行方式

```bash
cd frontend
npm run e2e:install
npm run e2e
```

带界面调试：

```bash
cd frontend
npm run e2e:headed
```

只跑当前权限流：

```bash
cd frontend
npx playwright test e2e/auth-rbac.spec.ts
```

## 4. 关键配置

- Playwright 配置文件：`frontend/playwright.config.ts`
- 默认前端端口：`4173`
- 默认后端端口：`8001`
- E2E 运行数据目录：`runtime/e2e/`
- 报告输出目录：`output/playwright/`

## 5. 后续扩展

当前基础设施已经够支撑后续场景继续增量补齐，优先顺序建议是：

1. `editor` 导入文档并在任务中心观察后台任务状态
2. `viewer` 浏览知识库但无法删除来源
3. `admin` 创建用户和工作区，再授权成员
4. 登录态刷新与未登录重定向的跨刷新持久化验证
