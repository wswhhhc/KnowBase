# 冒烟测试文档

## 1. 概述

**目标**: 快速验证 KnowBase 系统核心功能在部署或重大变更后是否正常工作。冒烟测试应在每次部署前执行，确保基本链路可用。

**测试范围**:
- 后端服务启动与健康检查
- 消息发送与回答生成
- 文档上传与处理
- 知识库浏览与搜索
- 对话管理 CRUD
- 前端页面渲染与交互

**前置条件**:
- 后端已启动（`uvicorn src.api.main:app --port 8000`）
- .env 配置了有效的 API Key
- 至少有一个已加载的文档

---

## 2. 冒烟测试用例

### 2.1 后端核心（服务启动）

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SMK-01 | 健康检查 | `GET /api/health` | 返回 `{"status": "ok"}`，HTTP 200 | P0 |
| SMK-02 | 知识库统计 | `GET /api/knowledge-base/stats` | 返回 `chunk_count ≥ 0` | P0 |
| SMK-03 | 知识库配置 | `GET /api/knowledge-base/config` | 返回 `chunk_size` 和 `chunk_overlap` | P0 |

### 2.2 消息发送

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SMK-04 | 基本问答 | `POST /api/chat/stream` 发问题 | SSE 收到 node/token/sources/done 事件 | P0 |
| SMK-05 | 对话创建 | `POST /api/conversations` | 返回含 id 和 thread_id 的对话 | P0 |
| SMK-06 | 消息列表 | `GET /api/conversations/{id}/messages` | 返回消息数组（可能为空） | P0 |

### 2.3 文档管理

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SMK-07 | 上传文档 | `POST /api/documents/upload` 上传 .txt | 返回 `chunk_count > 0` | P0 |
| SMK-08 | 来源列表 | `GET /api/knowledge-base/sources` | 来源名列表（可能为空） | P0 |

### 2.4 知识库浏览

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SMK-09 | 分块列表 | `GET /api/knowledge-base/chunks` | 返回 items + total 分页结构 | P0 |
| SMK-10 | 来源过滤 | `GET /api/knowledge-base/chunks?source=xxx` | 只返回该来源的 chunks | P0 |
| SMK-11 | 关键词搜索 | `GET /api/knowledge-base/chunks?search=keyword` | 返回匹配的 chunks | P1 |

### 2.5 对话管理

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SMK-12 | 对话列表 | `GET /api/conversations` | 返回数组（可能为空） | P0 |
| SMK-13 | 对话重命名 | `PATCH /api/conversations/{id}` | 标题已更新 | P1 |
| SMK-14 | 对话删除 | `DELETE /api/conversations/{id}` | 204 No Content | P1 |
| SMK-15 | 对话导出 | `GET /api/conversations/{id}/export` | 返回 Markdown 内容 | P1 |

### 2.6 指标面板

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SMK-16 | 查询日志 | `GET /api/metrics/logs` | 返回日志条目数组 | P1 |

### 2.7 前端

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SMK-17 | 前端页面加载 | 打开 `http://localhost:5173` | 页面渲染无白屏/JS 错误 | P0 |
| SMK-18 | 知识库浏览页 | 导航到 Browser 视图 | 片段列表显示，翻页正常 | P0 |
| SMK-19 | 指标面板 | 导航到 Dashboard 视图 | 统计卡片和图表渲染 | P0 |

---

## 3. 通过标准

- 所有 P0 冒烟用例 100% 通过
- 前端页面无控制台 JS 错误
- SSE 流式响应能在 30s 内完成

## 4. 执行方式

```bash
# 启动后端
cd backend && uv run uvicorn src.api.main:app --port 8000 &

# 运行冒烟测试（使用 unittest 或手动 curl）
cd backend && uv run python -m unittest tests.test_smoke -v

# 前端手动测试
# 打开 http://localhost:5173 验证基本功能
```
