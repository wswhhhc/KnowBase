# 后端结构说明

当前后端以 `backend/` 作为唯一 Python 应用根。

关键目录：

- `backend/src/api/`：FastAPI 路由、请求/响应模型、依赖注入
- `backend/src/config/`：typed settings、public settings、runtime overrides、constants
- `backend/src/graph/`：LangGraph 工作流、节点实现和路由逻辑
- `backend/src/rag/`：知识库导入、检索、catalog、向量存储适配
- `backend/src/persistence/`：SQLite repository 细节，以及团队版 Postgres 迁移路径的 SQLAlchemy engine/session 入口
- `backend/tests/`：后端测试

当前阶段的边界目标：

- `rag` 不再依赖 `api.models`
- `api/` 与测试辅助直接依赖 `persistence/`，不再经过 `conversations.py` 兼容层
- `graph/` 主路径直接使用 `history_nodes.py`、`generation_nodes.py`、`finalization_nodes.py`、`retrieval_nodes.py`、`quality_nodes.py`、`web_search_nodes.py`
- `DATABASE_URL` 是准生产团队版业务数据库入口；现有 repository 迁移完成前，默认值仍指向 `runtime/local/conversations.db`
