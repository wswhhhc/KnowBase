# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 运行 Streamlit 应用
uv run streamlit run src/app.py

# 运行所有测试
uv run python -m unittest discover -s tests

# 运行单个测试文件
uv run python -m unittest tests.test_knowledge_base
uv run python -m unittest tests.test_graph
uv run python -m unittest tests.test_utils
uv run python -m unittest tests.test_loaders
uv run python -m unittest tests.test_routing

# 运行单个测试方法
uv run python -m unittest tests.test_graph.GraphRoutingTests.test_run_query_uses_thread_memory_for_followup

# 包同步（安装依赖）
uv sync

# 离线 RAG 评估
uv run python -m unittest tests.<eval_module>  # see docs/rag_eval_dataset.jsonl
```

## Architecture

**KnowBase** — LangChain + LangGraph 知识库问答助手，Streamlit UI + Chroma 本地向量库 + BM25 混合检索。

### 核心模块

| 模块 | 职责 |
|------|------|
| **`src/app.py`** | Streamlit 入口。初始化知识库，管理会话消息，调用 LangGraph 工作流并显示流式进度。每个会话生成独立 `thread_id`（持久化到 `data/.thread_id`）。 |
| **`src/graph.py`** | LangGraph 工作流定义。节点：问题路由 → 查询改写 → 混合检索 → 重排序 → 生成回答 → 质量检查（不合格则扩检索重试）。`MemorySaver`  + `SqliteSaver` 保存线程状态。 |
| **`src/knowledge_base.py`** | 知识库核心。Chroma 向量库存储/检索，jieba BM25 索引，RRF 融合排序。`chunk_id` 基于 `source:chunk_index:content_hash[:16]` 稳定生成，基于 hash 去重。 |
| **`src/loaders.py`** | 多格式文档加载器。支持 `.txt` / `.md` / `.pdf` / `.docx` / `.html(.htm)`，返回 LangChain Document 列表。PDF 每页返回一个 Document（含 `page` 元数据）。 |
| **`src/utils.py`** | 文件上传校验（扩展名白名单和大小限制）和临时保存（`tempdir/knowbase_uploads/`）。 |
| **`src/metrics.py`** | RAG 查询本地 JSONL 日志，记录每次查询的耗时、检索数量、质量决策，写入 `data/rag_logs/rag_YYYY-MM-DD.jsonl`。 |
| **`config/settings.py`** | pydantic-settings 驱动，从 `.env` 读取配置，导出模块级常量。`CHROMA_API_KEY` 会回退作为 `SILICONFLOW_API_KEY`。 |

### LangGraph 工作流数据流

```
上传/预设文档 → TextLoader → RecursiveCharacterTextSplitter → Chroma 入库 + BM25 重建
用户提问 → route_question(正则路由) → rewrite_query(LLM改写) → hybrid_search(向量+BM25+RRF)
  → rerank_docs(LLM精排) → generate_answer → check_quality(LLM评判) → 不合格则扩检重试
```

路由分支（`route_after_classifier`）：knowledge_base → 检索问答；chat_memory → 会话记忆回答；conversation_summary → 会话总结；clarification → 模糊问题提示。

### RAG 评估

- `docs/rag_eval_dataset.jsonl` — 离线评估数据集，每行含 `question`、`reference`、`expected_type`，可用于 LangSmith evaluate。
- `docs/requirements.md` — 原始需求说明。

### 测试策略

- 单元测试用 `unittest`，mock LLM 调用（`FakeLLM` / `FakeResponse`）。
- `test_knowledge_base.py` — 纯函数逻辑（chunk_id 生成、RRF 融合、元数据回填）。
- `test_graph.py` — 用 mock LLM 测试路由分支、重试逻辑和线程记忆。
- `test_utils.py` — 文件名清洗、扩展名校验、大小限制。
- `test_loaders.py` — 多格式加载器，测试 `.txt` / `.md` / `.pdf` / `.docx` / `.html` 加载和元数据正确性。
- `test_routing.py` — 路由条件判断与 clarification 兜底逻辑。

### 关键约定

- 包管理用 `uv`，不用 pip。
- API Key 在 `.env` 中配置，`require_siliconflow_api_key()` 检查并抛出可读错误。
- LLM 和 embedding 都通过硅基流动 OpenAI-compatible API 调用。
- Chroma 持久化在 `data/chroma_db/`，`clear()` 会删除 collection 并重建。
- `all_docs` 在内存中维护 BM25 索引，重启时从 Chroma 恢复（`_load_existing_documents`）。
- `AGENTS.md` 是旧版参考，内容已被此文件覆盖。
- `.env` 中的 `CHROMA_API_KEY` 会回退作为 `SILICONFLOW_API_KEY`。
