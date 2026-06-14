# KnowBase 📚

基于 **LangChain + LangGraph** 的知识库问答助手。支持预设知识库问答和动态上传文档。

## 功能

- 预设知识库问答（内置 AI / Python / LangChain 三份文档）
- 动态上传 .txt/.md 文档到知识库
- 多轮对话
- 来源引用标注

## LangGraph 工作流

```
用户提问 → 查询改写 → 混合检索 → 重排序 → LLM 生成 → 质量检查 → 返回
                                           ↻ 不合格则重试
```

5 个节点：
1. **查询改写** — 结合对话历史优化问题
2. **混合检索** — 向量检索 + BM25 加权融合
3. **重排序** — LLM 精排
4. **生成回答** — 带来源引用的回答
5. **质量检查** — 检测幻觉/答非所问，不合格自动重试

## 技术栈

| 层 | 技术 |
|------|------|
| 框架 | LangChain |
| 编排 | LangGraph |
| UI | Streamlit |
| 向量库 | Chroma |
| Embedding | BAAI/bge-m3（硅基流动 API） |
| LLM | DeepSeek-V4-Flash（硅基流动 API） |

## 快速开始

### 1. 安装依赖

```bash
cd KnowBase
uv pip install -r requirements.txt
```

### 2. 配置 API Key

编辑 `config/settings.py`，填入你的硅基流动 API Key（已内置测试 Key）：

```python
SILICONFLOW_API_KEY = "你的 API Key"
```

### 3. 启动

```bash
uv run streamlit run src/app.py
```

浏览器打开 http://localhost:8501

## 项目结构

```
KnowBase/
├── config/settings.py       # 配置
├── data/                    # 预设文档 + Chroma 持久化
├── src/
│   ├── app.py              # Streamlit 主界面
│   ├── knowledge_base.py   # 知识库管理（加载/检索）
│   ├── graph.py            # LangGraph 工作流
│   └── utils.py            # 工具函数
├── docs/requirements.md    # 需求文档
└── requirements.txt
```
