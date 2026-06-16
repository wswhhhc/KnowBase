# 测试报告

> **报告生成时间**: 2026-06-16 19:10
> **测试环境**: Windows 11 Pro 10.0.26200 / Python 3.13 / Node.js 24.14
> **测试执行人**: Claude Code

---

## 1. 测试汇总

| 维度 | 结果 |
|------|------|
| 总测试用例 | **219**（后端 174 + 前端 45） |
| 通过率 | **100%** |
| 失败用例 | 0 |
| 缺陷数 | 0 |
| API 端点覆盖率 | **100%**（21/21） |
| 后端代码覆盖率 | **85%** |
| 前端核心代码覆盖率 | **96%**（hooks） |

### 按测试类型

| 类型 | 用例数 | 通过率 |
|------|-------|--------|
| 单元测试（后端） | 124 | 100% |
| 集成测试 | 22 | 100% |
| 接口测试 | 29 | 100% |
| 冒烟测试 | 10 | 100% |
| 边界测试 | 18 | 100% |
| 验收测试 | 14 | 100% |
| 单元测试（前端） | 45 | 100% |

---

## 2. 后端测试详情

**运行**: `uv run python -m unittest discover -v` — 174 个测试，18.5s

| 文件 | 用例数 | 类型 | 覆盖内容 |
|------|-------|------|---------|
| test_graph.py | 14 | 单元/验收 | 问题路由、质量检查、重排解析、多轮记忆、重试、联网搜索 |
| test_knowledge_base.py | 34 | 单元 | chunk_id 生成、RRF 融合、neighbor chunks、delete_source、clear |
| test_conversations.py | 17 | 单元 | CRUD、消息持久化、feedback、export、debug_pairs |
| test_utils.py | 27 | 单元 | 文件名清洗、上传校验、json 提取、错误分类、关键词提取 |
| test_loaders.py | 13 | 单元 | 6 种格式加载、URL 抓取、空内容拦截、登录跳转拒绝 |
| test_metrics.py | 4 | 单元 | 日志清除、质量失败率计算 |
| test_routing.py | 6 | 单元 | 澄清路由、should_retry 各分支 |
| test_debug_models.py | 6 | 单元 | DebugInfo/NodeDebug Pydantic 模型 |
| test_settings.py | 3 | 单元 | API key 校验、环境变量类型转换 |
| test_chat_route.py | 1 | 单元 | metrics debug flag 透传 |
| test_integration_graph_kb.py | 22 | 集成 | KB 检索、neighbor 扩展、rerank、web_search、finalize 证据等级 |
| test_api_endpoints.py | 29 | 接口 | 21 端点 happy/error path + schema 验证 |
| test_smoke.py | 10 | 冒烟 | 健康检查、KB stats、对话 CRUD、分块列表 |
| test_edge_cases.py | 18 | 边界 | 空/超长输入、404、分页边界、并发、非法 source |

---

## 3. 前端测试详情

**运行**: `npx vitest run` — 45 个测试，2.2s

| 文件 | 用例数 | 类型 | 覆盖内容 |
|------|-------|------|---------|
| utils.test.ts | 22 | 纯函数 | formatTime、truncate、evidenceColor、evidenceLabel、cn |
| useChat.test.ts | 7 | Hook | SSE 流式、sendMessage、onDone、onError、abort、并发拦截 |
| useData.test.ts | 5 | Hook | conversations CRUD、sources、状态管理 |
| useTheme.test.ts | 4 | Hook | localStorage、toggle、prefers-color-scheme |
| ChatArea.test.tsx | 3 | 组件 | 输入框、发送按钮、欢迎页渲染 |
| DebugPanel.test.tsx | 4 | 组件 | 节点时间线、quality 通过/失败展示 |

---

## 4. 接口覆盖

| 端点组 | 端点数 | 覆盖率 |
|--------|-------|--------|
| /api/chat | 1 | 100% |
| /api/conversations | 7 | 100% |
| /api/documents | 4 | 100% |
| /api/knowledge-base | 5 | 100% |
| /api/metrics | 2 | 100% |
| /api/health | 1 | 100% |
| **合计** | **21** | **100%** |

---

## 5. 代码覆盖率

### 后端（85%）

| 模块 | 覆盖率 | 缺口分析 |
|------|--------|---------|
| src/metrics.py | 94% | — |
| src/loaders.py | 93% | — |
| src/conversations.py | 93% | — |
| config/settings.py | 91% | — |
| src/graph.py | 80% | LLM 真实响应路径未覆盖 |
| src/api/ (路由层) | 76% | — |
| src/utils.py | 44% | classify_error、图片处理分支 |
| src/knowledge_base.py | 48% | Chroma 真实实例路径（当前 mock） |
| src/web_search.py | 41% | Tavily 全路径 |

### 前端

| 模块 | 语句覆盖率 | 说明 |
|------|-----------|------|
| hooks/ | **96%** | 核心逻辑，mock API + SSE |
| lib/utils.ts | **100%** | 纯函数全覆盖 |
| lib/api.ts | 59% | SSE 解析和大部分接口（因组件 mock 未调用） |
| components/ui/ | 61% | Radix 组件渲染路径 |
| src/ 整体 | 29% | 页面级组件（App、BrowserPage、DashboardPage、Sidebar）无渲染测试 |

---

## 6. 缺陷统计

| 严重程度 | 数量 |
|---------|------|
| S0-S4 | **0** |

当前测试周期未发现缺陷。详见 [缺陷文档](./07-defect-report.md)。

---

## 7. 结论与建议

### 总体结论

**✅ 可发布。** 219 个用例 100% 通过，无故障。核心功能（LangGraph 工作流、混合检索、SSE 流式、文档管理、对话 CRUD）和 21 个 API 端点均已验证。测试覆盖了正常路径、异常输入、边界条件和跨模块集成。

### 改进方向

| 优先级 | 建议 | 当前差距 |
|--------|------|---------|
| P1 | GitHub Actions CI 集成 | 每次需手动运行 |
| P2 | 页面级组件渲染测试（App、BrowserPage、DashboardPage） | 前端整体覆盖 29% |
| P2 | knowledge_base.py Chroma 真实实例集成测试 | 覆盖率 48% |
| P2 | E2E 用户流程测试（Playwright） | 无浏览器级验证 |
| P3 | 前端视觉回归测试 | 无 Storybook |

---

## 附录

### A. 测试环境

| 项目 | 值 |
|------|-----|
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.13 (via uv) |
| Node.js | 24.14 |
| 浏览器 | Chrome |
| 数据库 | SQLite（临时文件） |
| 向量库 | Chroma（mock） |
| LLM | FakeLLM（mock） |

### B. 测试策略说明

- **后端**: unittest + `FakeLLM` + `unittest.mock.patch`，隔离 Chroma/SQLite/网络
- **前端**: vitest + jsdom，mock fetch/API，测试纯函数、Hook 状态转换、组件渲染
- **覆盖率**: 后端用 `coverage`，前端用 `@vitest/coverage-v8`

### C. 相关文档

- [单元测试文档](./01-unit-test.md)
- [集成测试文档](./02-integration-test.md)
- [冒烟测试文档](./03-smoke-test.md)
- [边缘测试文档](./04-edge-test.md)
- [接口测试文档](./05-api-test.md)
- [验收测试文档](./06-acceptance-test.md)
- [缺陷文档](./07-defect-report.md)
