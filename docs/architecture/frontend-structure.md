# 前端结构说明

当前前端以 `frontend/` 作为唯一 Node 应用根。

关键目录：

- `frontend/src/app/`：应用壳、导航、入口装配
- `frontend/src/pages/`：页面级入口
- `frontend/src/features/`：功能状态与交互逻辑
- `frontend/src/shared/api/`：API client、SSE、错误处理与契约类型
- `frontend/src/components/`：通用组件和页面实现细节
- `frontend/src/test/`：Vitest 测试

当前阶段的边界目标：

- 根 `App.tsx` 只保留兼容入口
- 页面组件和 Sidebar 改从 `app/navigation.ts` 获取导航类型
- API client 不再集中在单个 `lib/api.ts`
- 知识库浏览的大 hook 开始向 `features/knowledge-browser/hooks/` 拆分
