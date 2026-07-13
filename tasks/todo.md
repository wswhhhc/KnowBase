# KnowBase 结构优化任务清单

## P0：后端 Documents

- [x] Task 1：锁定 Documents 路由行为
- [x] Task 2：抽取文档审计模块
- [x] Task 3：抽取后台任务 SSE 适配器
- [x] Task 4A：抽取文件与 URL 导入编排服务
- [x] Task 4B：抽取同步文档操作
- [x] Task 4C：抽取清空与重建任务契约
- [x] Task 5：固化后端结构边界
- [x] Checkpoint A：后端全量测试、OpenAPI 与结构守卫通过

## P0：前端 DocumentPanel

- [x] Task 6：抽取文档导入 hook
- [x] Task 7：抽取删除与清空 hook
- [x] Task 8：拆分 DocumentPanel 展示区块
- [x] Checkpoint B：前端全量测试、构建和 editor-jobs E2E 通过

## P1：页面级热点

- [x] Task 9：抽取 Dashboard 数据 hook 与纯指标模型
- [x] Task 10：拆分 Dashboard 独立展示区块
- [x] Task 11：统一 Chat 搜索偏好状态与控件
- [x] Task 11B：拆分 Chat 输入与消息区域
- [ ] Task 12：固化前端边界并同步文档
- [ ] Checkpoint C：仓库全量质量门禁与关键 E2E 通过

## P2：兼容债务

- [ ] Task 13：建立兼容路径退出清单

## 每项任务的完成门槛

- [ ] 仅包含当前任务范围内的改动
- [ ] 现有功能、接口、文案和错误行为保持不变
- [ ] 目标测试通过
- [ ] `python scripts/check-structure.py` 通过
- [ ] 阶段 Checkpoint 执行 `bash scripts/run-checks.sh`
- [ ] 无未使用 import、死代码或临时兼容 wrapper
- [ ] 提交说明使用中文
