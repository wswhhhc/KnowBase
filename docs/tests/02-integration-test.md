# 集成测试文档

## 1. 概述

**目标**: 验证 KnowBase 各模块之间的协作交互是否正确，包括数据流、接口契约和跨模块状态一致性。

**测试范围**:
- graph + knowledge_base 检索集成
- graph + conversations 持久化集成
- API routes + graph 流程集成
- KnowledgeBase + Chroma 生命周期集成
- conversations + SQLite CRUD 集成
- metrics + conversations 数据校正集成
- loaders + knowledge_base 文件入库集成

**Mock 策略**:
- LLM → `unittest.mock.patch('src.graph._get_llm')` → `FakeLLM`
- Tavily → `patch('src.web_search.web_search')` → 预设结果
- Chroma → 真实 Chroma 使用临时目录（非 mock）
- SQLite → 临时文件数据库

**前置条件**:
- 后端依赖已安装（`uv sync`）
- 临时目录有写入权限

---

## 2. 集成测试用例

### 2.1 graph + knowledge_base 集成

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| IT-GK-01 | `retrieve_docs` 节点使用 KB 混合检索 | 构造含 KB 的 graph → 触发 retrieve_docs | 返回 `RetrievalResult` 列表 | P0 |
| IT-GK-02 | 单文档 BM25 定位 | 注入 1 个文档到 KB，搜索相关内容 | 返回该文档 | P0 |
| IT-GK-03 | 多文档 RRF 融合排序 | 注入多个文档，执行混合检索 | 结果按 RRF 分数降序 | P0 |
| IT-GK-04 | neighbor chunk 扩展 | chunk 含前后邻居文档 | 扩展后结果数增多 | P1 |
| IT-GK-05 | quality check → expand_retrieval 重试 | LLM 返回质量不通过 | `kb.calls == 2` | P0 |
| IT-GK-06 | web_search 启用时的 generate_answer | KB 无结果 + web_search 有结果 | 答案含网络来源 | P0 |
| IT-GK-07 | SCORE_THRESHOLD 过滤 | 低分数候选被过滤 | 最终结果 ≤ 候选数 | P2 |

### 2.2 graph + conversations 集成

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| IT-GC-01 | `run_query` 结束后对话被持久化 | 调用 run_query → 检查 conversations | 对话含 user + assistant 消息 | P0 |
| IT-GC-02 | 同 thread 连续消息写入同一对话 | 同一 thread_id 两次 query | 共 4 条消息，顺序正确 | P0 |
| IT-GC-03 | debug_info 随消息写入 | run_query 完成 | debug_info 含检索链路信息 | P1 |

### 2.3 API routes + graph 集成

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| IT-API-01 | `POST /api/chat/stream` SSE 事件序列 | 发送合法 ChatRequest | 收到 node/token/sources/done 事件 | P0 |
| IT-API-02 | `/api/conversations` CRUD 完整生命周期 | 创建→发消息→取消息→删除 | 全部成功 | P0 |
| IT-API-03 | 上传文档后立即搜索 | 上传 .txt → 搜索相关词 | 返回该文档片段 | P0 |
| IT-API-04 | 删除 source 后搜索 | 删除 source → 同词搜索 | 不再返回 | P1 |
| IT-API-05 | 反馈提交后查询 | 点赞/点踩 → 查 message | feedback 字段已更新 | P1 |

### 2.4 KnowledgeBase + Chroma 完整生命周期

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| IT-KC-01 | ingest → search | 插入文档 → hybrid_search | 非空结果 | P0 |
| IT-KC-02 | ingest → delete → search | 插入→删除→搜索 | 该文档不出现 | P0 |
| IT-KC-03 | ingest → clear → search | 插入→清空→搜索 | 空结果 | P0 |
| IT-KC-04 | 多文档 ingest 后 source_counts | 插入 3 个来源 | 计数正确 | P1 |

### 2.5 conversations + SQLite 集成

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| IT-CS-01 | 数据库重建后数据完整 | init_db → 插入 → 重新 init_db | 数据仍可查询 | P0 |
| IT-CS-02 | 批量消息写入性能 | 100 条消息 | 全部成功写入，无锁冲突 | P2 |

### 2.6 metrics + conversations 数据校正

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| IT-MC-01 | debug 标志覆盖日志 flag | 日志含过时值，debug_info 含正确值 | 输出使用 debug_info 值 | P1 |

### 2.7 loaders + knowledge_base 文件入库

| 编号 | 测试用例 | 步骤 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| IT-LK-01 | ingest_file 完整链路 | 加载文件 → 切分 → Chroma 入库 | chunk_count > 0，可检索 | P0 |
| IT-LK-02 | ingest_url 完整链路 | 加载 URL → 处理 → Chroma 入库 | 来源含 url metadata | P0 |

---

## 3. Mock 策略汇总

| 模块 | 策略 | 说明 |
|------|------|------|
| `graph._get_llm` | `patch` 替换为 `FakeLLM` | 预设 LLM 响应，控制分支走向 |
| `web_search.web_search` | `patch` 返回预设结果/空 | 验证 web_search 启用/禁用 |
| `graph._tavily_configured` | `patch` 返回 `True`/`False` | 控制联网搜索开关 |
| Chroma | 使用 `tempfile.TemporaryDirectory` 真实实例 | 验证完整的 vectordb 生命周期 |
| SQLite | 临时文件（`tempfile.NamedTemporaryFile`） | 独立测试数据库 |
| `requests.get` | `patch` 返回 MockResponse | 避免真实 HTTP 请求 |

## 4. 通过标准

- 所有集成测试通过率 100%
- 各模块间数据传递无丢失/变形
- 跨模块事务一致性（如对话持久化与消息保存必须关联正确）

## 5. 执行方式

```bash
# 运行所有集成测试
cd backend && uv run python -m unittest tests.test_integration_graph_kb tests.test_integration_api -v
```
