# 性能测试文档

## 1. 概述

**目标**: 验证 KnowBase 系统在负载下的响应时间和资源消耗是否满足需求，确保核心链路的延迟预算可控。

**测试范围**:
- 各 LangGraph 节点的延迟分布
- 混合检索 + LLM 生成的端到端延迟
- 并发用户场景下的吞吐量
- 内存和 CPU 资源消耗

**前置条件**:
- 后端已启动（`uvicorn src.api.main:app --port 8000`）
- `.env` 配置了有效的 API Key
- 知识库至少包含 5 个以上来源的文档
- `locust` 已安装（`pip install locust`）

---

## 2. 延迟预算

### 2.1 单请求延迟分解

| 节点 | 预算 | 说明 |
|------|------|------|
| `route_question` | < 500ms | 正则 + LLM 分类（通常 200ms） |
| `rewrite_query` | < 300ms | 无历史时 < 5ms |
| `retrieve_docs` | < 2s | 混合检索（向量 + BM25） |
| `rerank_docs` | < 2s | LLM 精排（条件执行，非必走） |
| `generate_answer` | < 8s | LLM 生成回答 |
| `check_quality` | < 2s | LLM 质量检查（采样 1/3 概率） |
| **端到端** | **< 15s** | 含所有节点（无重试） |
| **端到端（重试）** | **< 30s** | 最多一次 expand + regenerate |

### 2.2 节点级指标

每个节点通过 `debug_info.nodes` 记录 `name`、`label`、`elapsed_ms`。性能测试应断言：

```
assert all(n.elapsed_ms < budget_ms for n in debug_info.nodes)
```

---

## 3. 负载测试方案

### 3.1 测试工具

使用 [Locust](https://locust.io/) 进行 HTTP 负载测试。

### 3.2 场景设计

| 场景 | 描述 | 权重 | 预期并发 |
|------|------|------|---------|
| 知识库问答 | `POST /api/chat/stream` 标准问题 | 70% | 10 并发 |
| 对话管理 | `GET/POST/DELETE /api/conversations` | 15% | 5 并发 |
| 知识库浏览 | `GET /api/knowledge-base/chunks` | 10% | 5 并发 |
| 文档上传 | `POST /api/documents/upload` 小文件 | 5% | 2 并发 |

### 3.3 Locust 脚本

```python
# backend/tests/load/locustfile.py
import json
from locust import HttpUser, task, between

class KnowBaseUser(HttpUser):
    wait_time = between(1, 3)

    @task(7)
    def chat_stream(self):
        with self.client.post(
            "/api/chat/stream",
            json={"question": "什么是 LangGraph？", "search_strategy": "balanced"},
            stream=True,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status: {resp.status_code}")

    @task(1)
    def list_conversations(self):
        self.client.get("/api/conversations")

    @task(1)
    def get_kb_chunks(self):
        self.client.get("/api/knowledge-base/chunks?skip=0&limit=10")

    @task(0.5)
    def get_kb_stats(self):
        self.client.get("/api/knowledge-base/stats")

    @task(0.5)
    def get_metrics_logs(self):
        self.client.get("/api/metrics/logs")
```

### 3.4 执行方式

```bash
# 启动 Locust Web UI
cd backend && locust -f tests/load/locustfile.py --host=http://localhost:8000

# 无头模式（10 用户，30s 预热，2min 持续）
locust -f tests/load/locustfile.py --host=http://localhost:8000 \
  --headless -u 10 -r 1 --run-time 2m30s
```

---

## 4. 性能指标和阈值

| 指标 | 阈值 | 测量方式 |
|------|------|---------|
| P50 端到端延迟 | < 8s | 日志中的 `elapsed_ms` |
| P95 端到端延迟 | < 20s | 日志中的 `elapsed_ms` |
| P99 端到端延迟 | < 30s | 日志中的 `elapsed_ms` |
| 质量通过率 | >= 80% | 日志中的 `quality_ok` |
| 内存增长 | < 200MB 持续 | `psutil` 或 Docker stats |
| SSE 事件完整性 | 100% | 收到 node/token/sources/done 序列 |

---

## 5. 执行方式

```bash
# 运行 Locust 负载测试
cd backend && locust -f tests/load/locustfile.py --host=http://localhost:8000 --headless -u 10 -r 1 --run-time 2m30s
```

## 6. 通过标准

- P95 端到端延迟 < 20s
- P99 端到端延迟 < 30s
- 质量通过率 >= 80%
- 无请求超时（> 60s）
- 无内存泄漏（持续运行 10 分钟后内存稳定）
