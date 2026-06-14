# KnowBase

基于 LangChain + LangGraph 的知识库问答助手。Streamlit UI、Chroma 本地向量库、候选集 BM25 + 向量混合检索，通过硅基流动 API 调用 LLM 和 embedding 模型。

## 功能

- 预设知识库问答和 `.txt` / `.md` / `.pdf` / `.docx` / `.html` 动态上传
- URL 一键导入网页内容
- LangGraph checkpoint 会话记忆 + 对话历史管理（新建/切换/删除/导出）
- 流式输出回答，边生成边展示
- 查询改写 → 候选集混合检索 → 条件式 LLM 精排 → 生成回答 → 分层质量检查
- 联网搜索兜底（可选 Tavily，侧边栏开关控制）
- 检索策略：fast / balanced / high_quality
- 邻居 chunk 上下文补全 + 标题追踪
- 知识库内容浏览与全文搜索
- 指标面板（耗时分布、质量通过率、每日趋势）
- 离线 RAG 评估脚本
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
TAVILY_API_KEY=tvly-xxx            # 联网搜索兜底
LANGSMITH_TRACING=false
CHUNK_SIZE=800
CHUNK_OVERLAP=50
TOP_K_RETRIEVAL=5
TOP_K_RERANK=3
VECTOR_CANDIDATE_K=30
```

启动：

```bash
uv run streamlit run src/app.py
```

## LangGraph 工作流

```text
用户提问
  → 问题路由（LLM 分类 + 正则兜底）
  → 查询改写（结合历史）/ 会话记忆 / 会话总结 / 模糊提示
  → 候选集混合检索（向量召回 30 条 → 候选 BM25 → RRF 融合）
  → 条件式 LLM 精排（分数差距大/短问题跳过）
  → 生成回答（带邻居 chunk 上下文 + 标题链）
  → 分层质量检查（规则层 → LLM 审核）
  → 不合格 → 联网搜索 / 扩检索重试 → 重新生成
```

每个 Streamlit 会话生成独立 `thread_id`，LangGraph checkpointer 保存线程消息历史。

## 检索与入库

- 切片策略：`RecursiveCharacterTextSplitter`（chunk_size=800, overlap=50），支持标题/段落/句末分割
- 每个 chunk 都带有 `chunk_id`、`source`、`source_type`、`chunk_index`、`section`（所属标题）、`content_hash`、`ingested_at`
- 相同来源和相同 chunk 不会重复入库（基于 chunk_id 去重）
- 混合检索：向量召回 N=30 条 → 候选集上做 BM25 → RRF 融合取 TopK
- 检索时自动补全前后邻居 chunk 作为上下文，减少断章取义
- 支持按 `source_type`（local_file / web_page）过滤检索范围

## 测试

```bash
# 全部测试
uv run python -m unittest discover -s tests

# 离线评估
uv run python -m src.evaluate
```

## 项目结构

```text
KnowBase/
├─ config/
│  └─ settings.py           # typed settings / .env 配置入口
├─ data/
│  ├─ sample_*.txt          # 预置知识文档
│  ├─ chroma_db/            # Chroma 持久化库
│  ├─ rag_logs/             # 查询日志 JSONL
│  └─ eval_reports/         # 离线评估报告
├─ docs/
│  ├─ requirements.md
│  └─ rag_eval_dataset.jsonl
├─ src/
│  ├─ app.py                # Streamlit 主入口
│  ├─ graph.py              # LangGraph 工作流
│  ├─ knowledge_base.py     # 入库与检索
│  ├─ loaders.py            # 多格式文档加载器 + URL 抓取
│  ├─ conversations.py      # 对话历史 SQLite 管理
│  ├─ web_search.py         # Tavily 联网搜索
│  ├─ kb_browser.py         # 知识库内容浏览
│  ├─ metrics.py            # 查询日志记录
│  ├─ evaluate.py           # 离线评估脚本
│  └─ metrics_dashboard.py  # 指标面板
├─ tests/
│  ├─ test_graph.py
│  ├─ test_knowledge_base.py
│  ├─ test_loaders.py
│  ├─ test_metrics.py
│  ├─ test_routing.py
│  ├─ test_settings.py
│  └─ test_utils.py
├─ .env
├─ .gitignore
├─ uv.lock
└─ pyproject.toml
```

