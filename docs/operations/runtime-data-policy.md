# 运行数据策略

KnowBase 把“样例”和“运行数据”明确分离：

## 版本控制内容

- `examples/demo-documents/`
- `examples/preset-documents/`

这些文件用于演示、测试和新人理解仓库，不应被程序运行时覆盖。

## 运行期内容

- `runtime/local/`
- `runtime/quickstart/`

这些目录用于：

- SQLite 数据库
- Chroma 持久化目录
- 查询日志
- 运行时设置覆盖
- 评估报告

它们默认忽略提交，提交前不要把本地产物强行纳入版本库。

准生产团队版会通过 `DATABASE_URL` 支持 Postgres 作为业务数据库。迁移完成前，本地默认值仍指向 `runtime/local/conversations.db`；Chroma、查询日志、运行时设置覆盖等本地运行数据仍继续遵守 `runtime/` 目录约定。

从本地 SQLite 迁移到 `DATABASE_URL` 时，先备份 `runtime/local/conversations.db`，再运行 `cd backend && uv run python scripts/import_sqlite_business_data.py --sqlite-path ../runtime/local/conversations.db --truncate`。脚本只导入 Phase 1 业务表：`workspaces`、`conversations`、`messages`、`bookmarks`、`pinned_sources`；Chroma 向量库仍按本地目录单独保留。

历史上遗留的根目录 `data/`、`backend/data/`，或误写入的 `backend/runtime/` 只视为本地残留，不再是受支持的运行数据根。新代码和新文档必须统一指向仓库根 `runtime/`。

如果本地仍保留旧 `data/` 或 `backend/data/`，推荐将其整体归档到 `runtime/archive/` 下按日期命名的目录，例如 `runtime/archive/root-data-legacy-20260615/` 或 `runtime/archive/backend-data-legacy-20260704/`，而不是继续让程序读写旧目录。

## quickstart 约定

- `scripts/quickstart.py` 只读取 `examples/demo-documents/`
- quickstart 运行数据只写入 `runtime/quickstart/`
- 默认应用运行目录与 quickstart 运行目录不能混用
