# 兼容路径退出清单

本清单记录仍保留的兼容路径及其退出条件。它不是删除计划的授权：删除实现、迁移数据或变更认证行为必须另立任务、单独评审，并通过完整回归验证。

目标版本统一为**不早于 v2.0.0**；具体版本须在下一个主版本规划中确认。

| 路径 | Owner | 当前证据与使用范围 | 移除前置条件 | 迁移与回滚 | 目标版本 |
|---|---|---|---|---|---|
| Legacy API Key | 后端认证与前端 API 客户端维护者 | `frontend/src/shared/api/client.ts` 在无 JWT 时读取 `knowbase_api_key`；`frontend/src/pages/settings/SettingsPage.tsx` 保存该值。后端 `backend/src/api/deps.py` 的 `get_current_user_or_legacy_api_key` 被 bookmarks、chat、conversations、jobs、knowledge_base、workspaces 路由直接使用，workspace/admin 权限依赖还会把兼容认证传播到 Documents、设置和指标等受保护路由。后端在 `settings.is_production` 时明确拒绝 API Key，因此仅限本地开发兼容。 | 统计或人工确认本地部署均已迁移到 JWT 登录；移除设置页的本地 Key 写入；将所有直接调用方及通过 workspace/admin 依赖间接接入的路由改为仅 JWT；更新前端认证、设置页、路由与权限测试。 | 迁移期保留 JWT 会话；若发布后本地开发认证受阻，回滚该独立删除提交，不回滚 RBAC/JWT 数据。 | 不早于 v2.0.0 |
| 旧 debug pin/exclude 字段 | Chat 状态与持久化维护者 | `frontend/src/hooks/chat/usePinnedSourcesState.ts` 在没有专用 pin state 时读取 `message.debugData.pinned` / `excluded`；主路径已是 `pinned_sources` 表、`pin_state_repository.py` 与 `/pin-state`。现有 `frontend/src/test/__tests__/hooks/useChat.test.ts` 覆盖“专用状态优先于 debug_info”。历史对话可能仍只有 debug payload。 | 对所有保留历史对话完成 pin state 回填，或确认可接受不迁移；增加迁移/回填脚本的幂等测试；移除 fallback 前保留导入、加载和回滚演练记录。 | 先备份业务库；通过可重复执行的回填任务把 debug 字段转换为 `pinned_sources`；若回填异常，停止切换并恢复备份，再继续读取旧字段。 | 不早于 v2.0.0 |
| 旧 Chroma 索引元数据 | RAG 与运行时数据维护者 | `backend/src/rag/knowledge_base.py` 读取/写入 `runtime/**/vector_store_meta.json` 的 `embedding_model`；缺失元数据时为已有索引回填，模型不一致时阻止检索/上传并要求清空重导。`backend/tests/test_knowledge_base.py` 覆盖 mismatch 与清空恢复。该路径涉及已落盘的本地向量索引。 | 盘点受支持运行目录中的元数据版本；提供索引元数据升级工具或明确要求重建；在迁移副本上验证模型不一致、缺失元数据和空索引三种场景。 | 先复制 Chroma 持久化目录和 `vector_store_meta.json`；升级失败时恢复目录副本，并继续使用当前兼容读取逻辑；不得原地删除未知 metadata。 | 不早于 v2.0.0 |

## 删除任务的共同门槛

1. 先建立单独 issue/任务，列出受影响 API、数据和用户路径。
2. 在 staging 或等价备份副本上演练迁移与回滚。
3. 添加移除后行为的回归测试，并删除只服务兼容路径的测试。
4. 更新 `README`、产品边界、运行手册和 OpenAPI/前端类型（如受影响）。
5. 以独立 PR 发布，不与结构重构、功能新增或依赖升级混合。
