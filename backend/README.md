# KnowBase Backend API

FastAPI backend with SSE streaming for the KnowBase RAG assistant.

## 配置

先从模板创建环境文件：

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## 启动

```bash
cd backend
uv sync
uv run uvicorn src.api.main:app --reload --port 8000
```

## 相关文档

- 根项目说明：[`README.md`](../README.md)
- 需求基线：[`docs/requirements.md`](../docs/requirements.md)
- 协作约定：[`CONTRIBUTING.md`](../CONTRIBUTING.md)
