# 单元测试文档

## 1. 概述

**目标**: 验证 KnowBase 各模块的纯函数和类方法在隔离环境下的正确性，确保每个最小可测试单元的行为符合预期。

**测试范围**:
- 后端: graph.py, knowledge_base.py, conversations.py, utils.py, loaders.py, metrics.py, web_search.py, api/models.py, config/settings.py
- 前端: lib/utils.ts, hooks/useTheme.ts, hooks/useChat.ts, hooks/useData.ts, lib/api.ts

**Mock 策略**: 
- LLM 调用 → `FakeLLM` 返回预设响应
- Chroma 向量库 → `unittest.mock.patch` 替换
- 网络请求 → `patch('requests.get')`
- 文件系统 → `tempfile.TemporaryDirectory`
- 前端 fetch → `vi.stubGlobal('fetch', mockFetch)`

**前置条件**:
- Python 3.10+，安装所有依赖（`cd backend && uv sync`）
- Node.js 18+，安装依赖（`cd frontend && npm install`）

---

## 2. 后端单元测试用例

### 2.1 graph.py — LangGraph 工作流

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-GRAPH-01 | `detect_question_type` 路由历史记忆问题 | 问"你知道上一次我问了你什么吗"，有历史 | `"chat_memory"` | P0 |
| UT-GRAPH-02 | `detect_question_type` 路由"刚刚问了什么" | 问"我刚刚问了什么"，有历史 | `"chat_memory"` | P0 |
| UT-GRAPH-03 | `detect_question_type` 路由总结问题 | 问"帮我总结一下刚才的对话"，有历史 | `"conversation_summary"` | P0 |
| UT-GRAPH-04 | `detect_question_type` 默认路由知识库 | 问"试用期年假怎么算"，有历史 | `"knowledge_base"` | P0 |
| UT-GRAPH-05 | `route_after_classifier` 记忆分支 | `question_type="chat_memory"` | `"answer_from_history"` | P0 |
| UT-GRAPH-06 | `route_after_retrieval` 空结果 | `documents=[]` | `"handle_missing_context"` | P0 |
| UT-GRAPH-07 | `route_after_rerank` 始终生成回答 | `web_search_enabled=True` | `"generate_answer"` | P0 |
| UT-GRAPH-08 | `parse_rerank_decision` 过滤无效 ID | `selected_doc_ids` 含不存在 ID | 只保留有效 ID | P1 |
| UT-GRAPH-09 | `parse_quality_decision` 解析 JSON 格式 | `{"quality_passed":false,…}` | `quality_passed=False` | P0 |
| UT-GRAPH-10 | `parse_quality_decision` 解析自然语言 | "回答准确引用了参考文档" | `quality_passed=True` | P1 |
| UT-GRAPH-11 | `parse_quality_decision` 非法 JSON fallback | 随机字符串 | `quality_passed=False` | P1 |
| UT-GRAPH-12 | `_should_rerank` 分数差距大时跳过 | RRF 分数差 > 阈值 | `False` | P2 |
| UT-GRAPH-13 | `_should_rerank` 短问题跳过 | 问题 < 50 字 | `False` | P2 |
| UT-GRAPH-14 | `_should_rerank` fast 策略跳过 | `search_strategy="fast"` | `False` | P2 |
| UT-GRAPH-15 | `_compute_evidence` 各等级计算 | 不同来源/分数组合 | 正确 `evidence_level` | P1 |
| UT-GRAPH-16 | `_messages_to_turns` 消息格式转换 | `(human, ai)` 消息列表 | 正确 `(question, answer)` 结构 | P1 |
| UT-GRAPH-17 | `_rule_check_quality` 规则层检查 | 含"没有找到"的回答 | `quality_passed=False` | P1 |
| UT-GRAPH-18 | `_initial_state` 默认状态 | 空参数 | 所有字段有默认值 | P2 |
| UT-GRAPH-19 | `run_query` 处理缺失上下文 | 空知识库，问题不相关内容 | 返回"没有找到足够相关" | P0 |
| UT-GRAPH-20 | `run_query` 多轮对话记忆 | 两轮对话使用同一 thread_id | 第二轮能回忆第一轮 | P0 |
| UT-GRAPH-21 | `run_query` 质量失败重试 | LLM 返回 quality_passed=false | `kb.calls == 2` | P0 |
| UT-GRAPH-22 | `run_query` 联网搜索启用 | web_search_enabled=True | 结果含 URL 来源 | P0 |

### 2.2 knowledge_base.py — 知识库核心

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-KB-01 | `_content_hash` 一致性 | 相同内容 | 相同 hash | P0 |
| UT-KB-02 | `_content_hash` 不同内容 | 不同字符串 | 不同 hash | P0 |
| UT-KB-03 | `_chunk_id` 格式 | source, index, hash | `"source:0:hash16"` | P0 |
| UT-KB-04 | `_documents_from_chroma_result` 恢复 content/metadata | Chroma get() 结果 | Document 列表含 chunk_id | P0 |
| UT-KB-05 | `_documents_from_chroma_result` 跳过空文档 | document="" | 跳过该条目 | P1 |
| UT-KB-06 | `_documents_from_legacy_chroma_ids` 回填 | UUID 格式 id | 回填 stable chunk_id | P1 |
| UT-KB-07 | `_prepare_splits` 添加 context 前缀 | Document 列表 | content 含"本段属于文档"前缀 | P0 |
| UT-KB-08 | 不同来源相同内容 → 不同 chunk_id | 相同内容不同 source | chunk_id 不同 | P1 |
| UT-KB-09 | `rrf_fuse` 融合排序 | vector_ranked + bm25_ranked | 按 RRF 分数降序排列 | P0 |
| UT-KB-10 | `rrf_fuse` limit 截断 | 10 个候选取 top 3 | 返回 3 条 | P1 |
| UT-KB-11 | `rrf_fuse` 空输入 | 两个空列表 | 空列表 | P2 |
| UT-KB-12 | `_document_chunk_id` 回填 metadata | Document 无 chunk_id | 自动生成并设置 | P1 |
| UT-KB-13 | `delete_source` 只删除目标 source | 删除 alpha.txt | beta.txt 保留 | P0 |
| UT-KB-14 | `delete_source` 减少 document_count | 删除一个 source | count 减少 | P0 |
| UT-KB-15 | `delete_source` 不存在 source 无操作 | 删除不存在 source | count 不变 | P1 |
| UT-KB-16 | `delete_source` 更新 BM25 索引 | 删除后 | BM25 索引同步更新 | P1 |
| UT-KB-17 | `source_counts` 多 source 统计 | 2 个 source | 正确计数 | P0 |
| UT-KB-18 | `get_neighbor_chunks` 边界窗口 | 首块 + window=1 | 相邻块 | P1 |
| UT-KB-19 | `get_neighbor_chunks` 不存在 chunk_id | 不存在的 id | 空列表 | P2 |
| UT-KB-20 | `clear()` 重置所有状态 | 有数据后 clear | 所有数据清空 | P0 |
| UT-KB-21 | `hybrid_search` 空知识库 | 无文档 | 空列表 | P1 |

### 2.3 conversations.py — 对话管理

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-CONV-01 | `create_conversation` 指定 thread_id 和 title | 自定义参数 | 返回匹配的 conv 对象 | P0 |
| UT-CONV-02 | `create_conversation` 自动生成 thread_id | 仅传 title | thread_id 不为空 | P1 |
| UT-CONV-03 | `get_conversation_by_thread` 存在 | 已创建的 thread | 返回 conv | P0 |
| UT-CONV-04 | `get_conversation_by_thread` 不存在 | 随机 thread | None | P1 |
| UT-CONV-05 | `get_conversation` 存在/不存在 | id | 返回或 None | P1 |
| UT-CONV-06 | `list_conversations` 排序 | 多条对话 | 按 updated_at 降序 | P0 |
| UT-CONV-07 | `list_conversations` 空表 | 无对话 | 空列表 | P2 |
| UT-CONV-08 | `update_title` 修改标题 | 新标题 | 标题已更新 | P1 |
| UT-CONV-09 | `update_title` 不存在对话 | 随机 id | 抛出或静默 | P2 |
| UT-CONV-10 | `delete_conversation` 删除 | 存在对话 | 删除成功，查询为 None | P0 |
| UT-CONV-11 | `delete_conversation` 级联删除消息 | 有消息的对话删除 | messages 表对应记录被删 | P1 |
| UT-CONV-12 | `add_message` 关联对话 | user/assistant 消息 | role 顺序正确 | P0 |
| UT-CONV-13 | `add_message` sources 字段 | 带 sources 的 assistant 消息 | sources JSON 正确存储/读取 | P1 |
| UT-CONV-14 | `add_message` debug_info 字段 | 带 JSON debug_info | 存储并正确解析 | P1 |
| UT-CONV-15 | `get_messages` 空对话 | 无消息 | 空列表 | P2 |
| UT-CONV-16 | `get_messages` 顺序 | 多条消息 | 按 created_at 升序 | P0 |
| UT-CONV-17 | `update_feedback` 设置反馈 | msg_id + feedback 字符串 | 反馈已记录 | P1 |
| UT-CONV-18 | `list_assistant_debug_pairs` 配对 | 多条消息 | debug_info 正确配对到前一条 user question | P1 |
| UT-CONV-19 | `export_conversation` Markdown 格式 | 有消息的对话 | 含 # 标题和消息的 Markdown | P1 |
| UT-CONV-20 | `export_conversation` 空对话 | 无消息 | 仅标题，无对话内容 | P2 |

### 2.4 utils.py — 工具函数

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-UTIL-01 | `sanitize_upload_filename` 去除路径 | `"../etc/passwd.txt"` | `"passwd.txt"` | P0 |
| UT-UTIL-02 | `sanitize_upload_filename` 拒绝空名 | `""` | `ValueError` | P1 |
| UT-UTIL-03 | `validate_upload` 拒绝超大文件 | 文件 > max_upload_mb | 返回 False | P0 |
| UT-UTIL-04 | `validate_upload` 拒绝不支持后缀 | `.exe` | 返回 False | P0 |
| UT-UTIL-05 | `validate_upload` 接受合法格式 | `.txt/.md/.pdf/.docx/.html/.htm` | 返回 True | P0 |
| UT-UTIL-06 | `json_from_text` 纯 JSON | `{"a":1}` | `{"a":1}` | P0 |
| UT-UTIL-07 | `json_from_text` Markdown 围栏 | `` ```json\n{"a":1}\n``` `` | `{"a":1}` | P1 |
| UT-UTIL-08 | `json_from_text` 无 JSON 内容 | 普通文本 | 原样返回或 None | P2 |
| UT-UTIL-09 | `classify_error` 认证错误 | 含"401"的异常 | 返回"认证失败" | P1 |
| UT-UTIL-10 | `classify_error` 限流错误 | 含"rate limit"的异常 | 返回"请求过于频繁" | P1 |
| UT-UTIL-11 | `classify_error` 未知错误 | 普通 Exception | 返回通用提示 | P2 |
| UT-UTIL-12 | `extract_context_terms` 简单句子 | "试用期年假怎么算" | 含"试用期""年假" | P0 |
| UT-UTIL-13 | `extract_context_terms` 空输入 | `""` | 空列表 | P1 |
| UT-UTIL-14 | `extract_context_terms` 纯停用词 | "的 了 是" | 空列表 | P1 |
| UT-UTIL-15 | `extract_context_terms` top_n 参数 | top_n=2 | 最多 2 个词 | P1 |
| UT-UTIL-16 | `format_chat_history` 消息转换 | `(human, ai)` 列表 | `(question, answer)` 列表 | P2 |

### 2.5 loaders.py — 文档加载器

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-LD-01 | `_load_text` 文本文件 | `.txt` 文件 | Document 含内容 | P0 |
| UT-LD-02 | `_load_md` Markdown 文件 | `.md` 文件 | Document 含内容 | P0 |
| UT-LD-03 | `_load_pdf` PDF 分页 | 多页 PDF | 每个 page 一个 Document | P0 |
| UT-LD-04 | `_load_docx` Word 文件 | `.docx` 文件 | Document 含合并内容 | P0 |
| UT-LD-05 | `_load_html` HTML 文件 | `.html` 文件 | 去除 script/style 标签 | P0 |
| UT-LD-06 | 不支持扩展名 | `.xyz` | `ValueError` | P0 |
| UT-LD-07 | `source_name` 参数覆盖 | 指定 source_name | metadata 使用指定名 | P1 |
| UT-LD-08 | `.htm` 后缀 | `.htm` 文件 | 正常加载 | P1 |
| UT-LD-09 | `load_url` 提取主内容 | 正常 URL | 保留 `<main>`，去除 `<nav>` | P0 |
| UT-LD-10 | `load_url` 自定义 source_name | URL + 自定义名 | metadata 使用指定名 | P1 |
| UT-LD-11 | `load_url` 拒绝登录跳转 | 跳转到飞书/登录页 | 抛出异常 | P0 |
| UT-LD-12 | `load_url` 空内容 | 提取后内容为空 | 抛出异常 | P1 |
| UT-LD-13 | `load_url` HTML 含 title 标签 | 有 `<title>` 的页面 | metadata 含 title | P1 |

### 2.6 metrics.py — 指标日志

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-MET-01 | `clear_today_log` 清除存在文件 | 模拟日志目录 | 文件被删除 | P1 |
| UT-MET-02 | `clear_today_log` 文件不存在 | 空目录 | 返回 False | P1 |
| UT-MET-03 | `quality_fail_rate` 全量 N 行 | 10 行含 5 行失败 | 50% | P1 |
| UT-MET-04 | `quality_fail_rate` 最近 N 行 | N=2 无失败 | 0% | P1 |
| UT-MET-05 | `quality_fail_rate` 空 DataFrame | 空数据 | 0% 或异常 | P2 |
| UT-MET-06 | `log_query` 基本记录 | 字段数据 | JSONL 文件含正确内容 | P0 |
| UT-MET-07 | `log_query` question 截断 | 超 100 字符 question | 只存前 100 字符 | P2 |

### 2.7 web_search.py

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-WEB-01 | `format_search_results` 标准结果 | 含 title/url/content | 格式化的文本 | P1 |
| UT-WEB-02 | `format_search_results` 空结果 | 空列表 | 空字符串 | P2 |

### 2.8 api/models.py

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-MOD-01 | `ChatRequest` 合法请求 | `question="你好"` | 验证通过 | P0 |
| UT-MOD-02 | `ChatRequest` question 为空 | `question=""` | 验证失败 | P0 |
| UT-MOD-03 | `ChatRequest` question 超长 | `"a"*4097` | 验证失败 | P1 |
| UT-MOD-04 | `DebugInfo` 默认值 | 空构造 | 所有可选字段为 None | P0 |
| UT-MOD-05 | `DebugInfo` 含 nodes | `nodes=[NodeDebug(...)]` | 正确序列化/反序列化 | P0 |
| UT-MOD-06 | `NodeDebug` 构造 | `name="retrieve", elapsed_ms=100` | 字段正确 | P0 |
| UT-MOD-07 | `QueryLogEntry` 构造 | 完整字段 | 验证通过 | P1 |

### 2.9 config/settings.py

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-CFG-01 | `_is_configured_api_key` 拒绝空/占位符 | `""` / `"你的 API Key"` / `"abc123"` | False | P0 |
| UT-CFG-02 | `_is_configured_api_key` 接受合法 key | `"sk-1234567890"` | True | P0 |
| UT-CFG-03 | Settings 环境变量类型 | env 字符串→int/bool | 类型转换正确 | P1 |

---

## 3. 前端单元测试用例

### 3.1 lib/utils.ts

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-FE-01 | `cn` 合并 class | `"px-4", "py-2"` | `"px-4 py-2"` | P0 |
| UT-FE-02 | `cn` 去重 | `"px-4 px-4"` | `"px-4"` | P1 |
| UT-FE-03 | `formatTime` 30 秒内 | 30s 前 | `"刚刚"` | P0 |
| UT-FE-04 | `formatTime` 5 分钟前 | 5min 前 | `"5 分钟前"` | P0 |
| UT-FE-05 | `formatTime` 2 小时前 | 2h 前 | `"2 小时前"` | P0 |
| UT-FE-06 | `formatTime` 3 天前 | 3d 前 | `"3 天前"` | P1 |
| UT-FE-07 | `formatTime` 超过 7 天 | 10d 前 | locale 日期字符串 | P1 |
| UT-FE-08 | `truncate` 短字符串 | `"hello"`, len=10 | `"hello"` | P0 |
| UT-FE-09 | `truncate` 超长字符串 | `"hello world"`, len=5 | `"hello…"` | P0 |
| UT-FE-10 | `evidenceColor` 各级别颜色 | `high/medium/low/none` | 对应 Tailwind class | P1 |
| UT-FE-11 | `evidenceLabel` 各级别中文 | `high/medium/low/none` | 对应中文标签 | P1 |

### 3.2 hooks/useTheme.ts

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-FE-12 | 初始读取 localStorage | 无存储 | 默认值或 `prefers-color-scheme` | P0 |
| UT-FE-13 | toggle 切换主题 | `dark→light` | HTML class 更新 | P0 |
| UT-FE-14 | localStorage 持久化 | toggle 后刷新 | 保持上次选择 | P0 |
| UT-FE-15 | `document.documentElement` class 操作 | 切换 | add/remove 正确 | P1 |

### 3.3 hooks/useChat.ts

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-FE-16 | sendMessage 添加 user/assistant 消息 | `question="你好"` | messages 末尾追加 2 条 | P0 |
| UT-FE-17 | onToken 累积 | 多个 token 事件 | content 逐步拼接 | P0 |
| UT-FE-18 | onDone 最终状态 | SSE done 事件 | streaming=false，消息更新 | P0 |
| UT-FE-19 | onError 错误处理 | SSE error 事件 | 错误消息显示 | P1 |
| UT-FE-20 | stopStreaming 中断 | AbortController | 状态重置 | P1 |
| UT-FE-21 | clearMessages | 有消息 | 数组清空，threadId 重置 | P0 |
| UT-FE-22 | loadMessages 加载历史 | 历史消息列表 | state 恢复 | P0 |
| UT-FE-23 | isStreaming 时阻止并发 | 正在 streaming | sendMessage 返回 | P1 |

### 3.4 hooks/useData.ts

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-FE-24 | useConversations 初始 fetch | 无 | 加载对话列表 | P0 |
| UT-FE-25 | create 后 refresh | 创建新对话 | 列表包含新条目 | P1 |
| UT-FE-26 | remove 后刷新 + 清除 activeId | 删除当前 active 对话 | activeId 置空 | P1 |
| UT-FE-27 | rename 后更新 | 新标题 | 列表更新 | P1 |
| UT-FE-28 | useSources refresh | 无 | 加载来源列表 | P1 |

### 3.5 lib/api.ts

| 编号 | 测试用例 | 输入 | 预期输出 | 优先级 |
|------|---------|------|---------|--------|
| UT-FE-29 | `chatStream` SSE node 事件解析 | SSE 数据流 | onNode 回调触发 | P0 |
| UT-FE-30 | `chatStream` SSE token 事件 | token 数据 | onToken 回调触发 | P0 |
| UT-FE-31 | `chatStream` SSE done 事件 | 完成数据 | onDone 回调触发 | P0 |
| UT-FE-32 | `chatStream` HTTP 错误 | 500 响应 | onError 回调触发 | P1 |

---

## 4. 通过标准

- 所有测试用例 100% 通过
- 无 flaky 测试（同一环境连续运行 3 次结果一致）
- Mock 使用正确，无泄漏到外部系统
- 前端测试无真实 API 调用

## 5. 执行方式

```bash
# 后端单元测试
cd backend && uv run python -m unittest discover -v

# 前端单元测试
cd frontend && npx vitest run
```
