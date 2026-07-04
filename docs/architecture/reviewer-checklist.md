# 结构 Reviewer Checklist

审查结构类改动时，至少确认以下事项：

- 后端命令是否都以 `backend/` 作为 Python 应用根执行
- 运行期数据是否只写入 `runtime/`
- 版本化样例是否只放在 `examples/`
- `rag/`、`graph/` 是否没有反向依赖 API 层模型
- 前端组件是否没有从根 `App.tsx` 反向导入类型
- `shared/api/` 的新增逻辑是否没有重新堆回 `lib/api.ts`
- OpenAPI 快照和前端生成类型是否已同步更新
- README / CONTRIBUTING / 相关 docs 是否与代码结构一致
