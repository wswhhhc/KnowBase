# 接口测试文档

## 1. 概述

**目标**: 验证 KnowBase 所有 REST API 端点的请求/响应正确性，包括状态码、响应体 Schema、错误处理和认证。

**测试范围**: 所有 27 个公开 API 端点

**前置条件**:
- FastAPI TestClient 可用
- 临时数据库和 mock KnowledgeBase

**运行方式**:
```bash
cd backend && uv run python -m unittest tests.test_api_endpoints -v
```

---

## 2. API 端点清单

### 2.1 Chat — `/api/chat`

#### POST `/api/chat/stream` — SSE 流式聊天

| 编号 | 测试用例 | 请求体 | 预期状态码 | 预期响应 |
|------|---------|--------|-----------|---------|
| API-CHAT-01 | 合法聊天请求 | `{"question":"你好","search_strategy":"balanced"}` | 200 | SSE 流，含 node/token/sources/done 事件 |
| API-CHAT-02 | question 为空 | `{"question":""}` | 422 | 验证错误 |
| API-CHAT-03 | question 超长 | `{"question":"a"*4097}` | 422 | 验证错误 |
| API-CHAT-04 | 缺少 question | `{}` | 422 | 验证错误 |
| API-CHAT-05 | 额外字段忽略 | `{"question":"hi","extra":"ignored"}` | 200 | 正常处理 |

### 2.2 Conversations — `/api/conversations`

#### GET `/api/conversations` — 对话列表

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-CONV-01 | 空列表 | 200 | `[]` | P0 |
| API-CONV-02 | 有数据 | 200 | `ConversationOut[]` 按 updated_at 降序 | P0 |
| API-CONV-03 | 请求头不含 Content-Type | 200 | 正常返回（GET 无需 body） | P2 |

#### POST `/api/conversations` — 创建对话

| 编号 | 测试用例 | 请求体 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|--------|-----------|---------|--------|
| API-CONV-04 | 创建默认标题 | `{}` | 200 | 含 id, thread_id, title="新对话" | P0 |
| API-CONV-05 | 创建自定义标题 | `{"title":"测试"}` | 200 | title="测试" | P0 |

#### GET `/api/conversations/{id}` — 获取单个对话

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-CONV-06 | 存在 | 200 | ConversationOut | P0 |
| API-CONV-07 | 不存在 | 404 | `{"detail":"Conversation not found"}` | P0 |

#### PATCH `/api/conversations/{id}` — 重命名对话

| 编号 | 测试用例 | 请求体 | 预期状态码 | 优先级 |
|------|---------|--------|-----------|--------|
| API-CONV-08 | 重命名 | `{"title":"新标题"}` | 200 | P1 |
| API-CONV-09 | 不存在对话 | `{"title":"新标题"}` | 404 | P1 |

#### DELETE `/api/conversations/{id}` — 删除对话

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-CONV-10 | 存在对话 | 204 | 无内容 | P0 |
| API-CONV-11 | 不存在对话 | 404 | `{"detail":"..."}` | P1 |

#### GET `/api/conversations/{id}/messages` — 消息列表

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-CONV-12 | 空消息 | 200 | `[]` | P0 |
| API-CONV-13 | 有消息 | 200 | `MessageOut[]` 含 role/content/sources | P0 |
| API-CONV-14 | 不存在对话 | 404 | - | P1 |

#### POST `/api/conversations/{id}/messages/{msg_id}/feedback` — 反馈

| 编号 | 测试用例 | 请求体 | 预期状态码 | 优先级 |
|------|---------|--------|-----------|--------|
| API-CONV-15 | 合法反馈 | `{"feedback":"👍"}` | 200 | P1 |
| API-CONV-16 | 不存在消息 | `{"feedback":"👍"}` | 404 | P2 |

#### GET `/api/conversations/{id}/export` — 导出 Markdown

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-CONV-17 | 有消息 | 200 | `{"markdown":"..."}` 含 # 标题 | P1 |
| API-CONV-18 | 空对话 | 200 | Markdown 仅含标题 | P2 |

### 2.3 Documents — `/api/documents`

#### GET `/api/documents/sources` — 来源列表

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-DOC-01 | 正常 | 200 | `[{"source":"a.txt","count":3}]` | P0 |

#### POST `/api/documents/upload` — 上传文档

| 编号 | 测试用例 | 文件 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|------|-----------|---------|--------|
| API-DOC-02 | 上传 .txt | sample.txt | 200 | `{"chunk_count":N,"total_docs":M}` | P0 |
| API-DOC-03 | 上传 .md | sample.md | 200 | chunk_count > 0 | P0 |
| API-DOC-04 | 上传非法格式 | test.exe | 422/400 | 错误提示 | P0 |
| API-DOC-05 | 不上传文件 | - | 422 | - | P1 |
| API-DOC-06 | 同时上传多文件 | 2 个文件 | 200 | 总 chunk_count 正确 | P2 |

#### POST `/api/documents/ingest-url` — URL 导入

| 编号 | 测试用例 | 请求体 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|--------|-----------|---------|--------|
| API-DOC-07 | 合法 URL | `{"url":"https://example.com"}` | 200 | `{"chunk_count":N}` | P0 |
| API-DOC-08 | URL 为空 | `{"url":""}` | 422 | - | P1 |
| API-DOC-09 | URL 格式非法 | `{"url":"not-a-url"}` | 422 | - | P1 |

#### DELETE `/api/documents/source/{name}` — 删除来源

| 编号 | 测试用例 | 参数 | 预期状态码 | 优先级 |
|------|---------|------|-----------|--------|
| API-DOC-10 | 存在来源 | name 编码 | 200 | P1 |
| API-DOC-11 | 不存在来源 | "nonexistent" | 200（幂等） | P2 |

#### POST `/api/documents/clear` — 清空知识库

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-DOC-12 | 清空 | 200 | `{"message":"知识库已清空"}` | P0 |

### 2.4 Knowledge Base — `/api/knowledge-base`

#### GET `/api/knowledge-base/stats` — 统计

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-KB-01 | 有数据 | 200 | `{"chunk_count":N,"source_count":M,"total_chars":L}` | P0 |
| API-KB-02 | 空知识库 | 200 | `{"chunk_count":0,"source_count":0,"total_chars":0}` | P0 |

#### GET `/api/knowledge-base/chunks` — 分块列表

| 编号 | 测试用例 | 参数 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|------|-----------|---------|--------|
| API-KB-03 | 默认分页 | 无 | 200 | `{"items":KBChunk[],"total":N}` | P0 |
| API-KB-04 | 指定 skip/limit | `?skip=0&limit=5` | 200 | 最多 5 条 | P0 |
| API-KB-05 | 来源过滤 | `?source=xxx` | 200 | 只返回该 source | P0 |
| API-KB-06 | 关键词搜索 | `?search=keyword` | 200 | 匹配结果 | P1 |
| API-KB-07 | limit=0 | `?limit=0` | 200 | 空 items | P2 |
| API-KB-08 | skip 超出范围 | `?skip=9999` | 200 | 空 items | P1 |

#### GET `/api/knowledge-base/sources` — 来源名列表

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-KB-09 | 正常 | 200 | `["source1.txt","source2.md"]` | P0 |

#### GET `/api/knowledge-base/config` — 配置

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-KB-10 | 正常 | 200 | `{"chunk_size":500,"chunk_overlap":50}` | P0 |

#### GET `/api/knowledge-base/hotspots` — 热点追踪

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-KB-11 | 正常 | 200 | `HotspotEntry[]` | P1 |

### 2.5 Metrics — `/api/metrics`

#### GET `/api/metrics/logs` — 查询日志

| 编号 | 测试用例 | 参数 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|------|-----------|---------|--------|
| API-MET-01 | 默认参数 | 无 | 200 | `QueryLogEntry[]` | P0 |
| API-MET-02 | 指定天数 | `?days=7` | 200 | 过滤日期 | P1 |
| API-MET-03 | 限制条数 | `?limit=10` | 200 | 最多 10 条 | P1 |

#### DELETE `/api/metrics/logs/today` — 清除当日日志

| 编号 | 测试用例 | 预期状态码 | 优先级 |
|------|---------|-----------|--------|
| API-MET-04 | 清除 | 200 | P2 |

### 2.6 Workspaces — `/api/workspaces`

| 编号 | 测试用例 | 方法 | 预期状态码 | 优先级 |
|------|---------|------|-----------|--------|
| API-WS-01 | 列表 | GET | 200 | P0 |
| API-WS-02 | 创建 | POST | 200 | P0 |
| API-WS-03 | 更新 | PATCH | 200 | P1 |
| API-WS-04 | 删除 | DELETE | 200 | P1 |
| API-WS-05 | 更新不存在 | PATCH /nonexist | 404 | P1 |
| API-WS-06 | 删除不存在 | DELETE /nonexist | 404 | P1 |

### 2.7 Bookmarks — `/api/bookmarks`

| 编号 | 测试用例 | 方法 | 预期状态码 | 优先级 |
|------|---------|------|-----------|--------|
| API-BM-01 | 列表 | GET | 200 | P0 |
| API-BM-02 | 创建 | POST | 200 | P0 |
| API-BM-03 | 删除 | DELETE | 200 | P1 |
| API-BM-04 | 按工作区过滤 | GET ?workspace_id=xxx | 200 | P1 |

### 2.8 Health — `/api/health`

| 编号 | 测试用例 | 预期状态码 | 预期响应 | 优先级 |
|------|---------|-----------|---------|--------|
| API-HLTH-01 | 健康检查 | 200 | `{"status":"ok"}` | P0 |

---

## 3. 响应 Schema 验证

每个端点需要验证：
1. **状态码**：符合预期（200/204/404/422）
2. **Content-Type**：`application/json`（SSE 端点除外）
3. **响应体字段完整性**：所有必填字段存在且类型正确
4. **错误响应格式**：`{"detail": "..."}` 格式统一

## 4. 通过标准

- 所有 27 个端点至少 1 个 happy path + 1 个 error path 测试通过
- 响应 Schema 与 Pydantic 模型定义一致
- 无意外 500 错误

## 5. 执行方式

```bash
cd backend && uv run python -m unittest tests.test_api_endpoints -v
```
