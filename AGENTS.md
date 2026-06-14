# KnowBase — AGENTS.md

## 项目概览

LangChain + LangGraph 知识库问答助手，Streamlit UI，Chroma 向量库，API 调用硅基流动。

## 启动方式

```bash
uv run streamlit run src/app.py
```

## 目录结构

- `src/app.py` — Streamlit 入口
- `src/knowledge_base.py` — 知识库（加载/分割/嵌入/检索）
- `src/graph.py` — LangGraph 工作流定义
- `src/utils.py` — 上传校验与通用工具
- `config/settings.py` — `.env` 驱动的应用配置
- `tests/` — 单元测试与回归测试
- `docs/` — 需求文档与离线评估样例
- `data/` — 预设文档 + Chroma 持久化数据

## 关键约定

- 包管理用 **uv**，不用 pip
- API Key 在 `.env` 中配置
- 知识库数据持久化在 `data/chroma_db/`
