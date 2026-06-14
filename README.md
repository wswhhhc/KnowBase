# KnowBase

基于 LangChain + LangGraph 的知识库问答助手。项目使用 Streamlit UI、Chroma 本地向量库、BM25 + 向量混合检索，并通过硅基流动 OpenAI-compatible API 调用 LLM 和 embedding 模型。

## 功能

- 预设知识库问答和 `.txt` / `.md` 动态上传
- LangGraph checkpoint 会话记忆
- 查询改写、混合检索、结构化重排、答案生成、质量检查
- Streaming 节点进度展示
- 引用来源、chunk 分数和质量检查说明
- LangSmith tracing 配置入口

## 快速开始

```bash
cd KnowBase
uv sync
```

创建或编辑 `.env`：

```env
SILICONFLOW_API_KEY=你的硅基流动密钥
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
EMBEDDING_MODEL=BAAI/bge-m3

# 可选
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
MAX_UPLOAD_MB=5
CHUNK_SIZE=500
CHUNK_OVERLAP=100
TOP_K_RETRIEVAL=5
TOP_K_RERANK=3
```

启动：

```bash
uv run streamlit run src/app.py
```

## LangGraph 工作流

```text
用户提问
  -> 问题路由
  -> 查询改写 / 会话记忆 / 会话总结
  -> 混合检索
  -> 结构化重排
  -> 生成回答
  -> 质量检查
  -> 不合格时扩大检索重试
```

每个 Streamlit 会话会生成独立 `thread_id`，LangGraph checkpointer 会保存该线程内的消息历史。

## 检索与入库

- 每个 chunk 都带有 `chunk_id`、`source`、`chunk_index`、`content_hash`、`ingested_at`。
- 相同来源和相同 chunk 不会重复入库。
- 混合检索使用向量召回 + jieba BM25，并通过 RRF 融合排序。
- 上传文件会执行文件名清洗、扩展名校验和大小限制。

## 测试

```bash
uv run python -m unittest discover -s tests
```

离线 RAG 评估样例数据位于 `docs/rag_eval_dataset.jsonl`，可用于接入 LangSmith evaluate。

## 项目结构

```text
KnowBase/
├─ config/
│  └─ settings.py           # typed settings / .env 配置入口
├─ data/
│  ├─ sample_*.txt          # 预置知识文档
│  └─ chroma_db/            # Chroma 持久化库
├─ docs/
│  ├─ requirements.md       # 需求说明
│  └─ rag_eval_dataset.jsonl
├─ src/
│  ├─ app.py                # Streamlit UI
│  ├─ graph.py              # LangGraph 工作流
│  ├─ knowledge_base.py     # 入库与检索
│  └─ utils.py              # 上传校验等工具
├─ tests/
│  └─ test_*.py             # 单元与回归测试
├─ .env
├─ AGENTS.md
├─ pyproject.toml
├─ requirements.txt
└─ uv.lock
```
