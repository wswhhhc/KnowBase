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

## quickstart 约定

- `scripts/quickstart.py` 只读取 `examples/demo-documents/`
- quickstart 运行数据只写入 `runtime/quickstart/`
- 默认应用运行目录与 quickstart 运行目录不能混用
