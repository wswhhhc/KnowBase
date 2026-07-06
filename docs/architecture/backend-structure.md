# 后端结构说明

当前后端以 `backend/` 作为唯一 Python 应用根。

关键目录：

- `backend/src/api/`：FastAPI 路由、请求/响应模型、依赖注入
- `backend/src/config/`：typed settings、public settings、runtime overrides、constants
- `backend/src/graph/`：LangGraph 工作流、节点实现和路由逻辑
- `backend/src/rag/`：知识库导入、检索、catalog、向量存储适配
- `backend/src/persistence/`：SQLAlchemy engine/session、Postgres/SQLite repository 适配、认证/任务/审计持久化
- `backend/src/jobs/`：Redis RQ 队列、worker 入口和导入/清空/重建索引后台任务
- `backend/tests/`：后端测试

当前阶段的边界目标：

- `rag` 不再依赖 `api.models`
- `api/` 与测试辅助直接依赖 `persistence/`，不再经过 `conversations.py` 兼容层
- `graph/` 主路径直接使用 `history_nodes.py`、`generation_nodes.py`、`finalization_nodes.py`、`retrieval_nodes.py`、`quality_nodes.py`、`web_search_nodes.py`
- `DATABASE_URL` 是准生产团队版业务数据库入口；生产模式必须指向 Postgres，本地开发默认仍可使用 `runtime/local/conversations.db`
