# 安全测试文档

## 1. 概述

**目标**: 验证 KnowBase 系统在输入校验、访问控制、数据保护和外部依赖方面的安全性，确保无常见 Web 安全漏洞。

**测试范围**:
- 输入校验（XSS、SQL 注入、超长输入）
- 文件上传安全
- URL 导入安全（SSRF）
- API 访问控制
- 敏感信息泄露
- 依赖安全

---

## 2. 安全测试用例

### 2.1 输入校验

| 编号 | 测试用例 | 输入 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SEC-INPUT-01 | XSS 在 question 中 | `"<script>alert('xss')</script>"` | 作为普通文本处理，不执行 | P0 |
| SEC-INPUT-02 | XSS 在对话标题中 | `"<img src=x onerror=alert(1)>"` | 存储原样，前端展示时转义 | P0 |
| SEC-INPUT-03 | SQL 注入在 conv_id | `"1; DROP TABLE messages"` | 返回 404，不执行 SQL | P0 |
| SEC-INPUT-04 | SQL 注入在 source 名 | `"a.txt'; DELETE FROM..."` | 作为普通文件名处理 | P1 |
| SEC-INPUT-05 | 超长 question 注入 | 4097 字符 `"A"*4097` | 返回 422 | P0 |
| SEC-INPUT-06 | 超长对话标题 | 1000 字符标题 | 截断或返回 422 | P1 |
| SEC-INPUT-07 | Unicode 溢出 | 包含零宽字符/控制字符 | 正常处理或过滤 | P2 |
| SEC-INPUT-08 | JSON 深度嵌套 | 深度 100 层嵌套 JSON | 解析失败返回 422 | P2 |

### 2.2 文件上传安全

| 编号 | 测试用例 | 输入 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SEC-FILE-01 | 路径遍历文件名 | `"../../../etc/passwd.txt"` | sanitize 为 `passwd.txt` | P0 |
| SEC-FILE-02 | 空文件名 | `""` | 拒绝上传 | P1 |
| SEC-FILE-03 | 超长文件名 | 255+ 字符 | 截断或拒绝 | P1 |
| SEC-FILE-04 | 二进制伪装文本 | `.txt` 但含空字节 | 加载后内容不变 | P2 |
| SEC-FILE-05 | 超大文件 | 超过 `max_upload_mb` | 返回 413 或校验错误 | P0 |
| SEC-FILE-06 | 不支持的扩展名 | `.exe`, `.bat`, `.sh` | 返回 422 | P0 |
| SEC-FILE-07 | 文件名含特殊字符 | `"test (1) & ;.txt"` | 正常处理 | P2 |

### 2.3 URL 导入安全（SSRF）

| 编号 | 测试用例 | 输入 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SEC-URL-01 | 内网 IP | `http://127.0.0.1` | 拒绝请求 | P0 |
| SEC-URL-02 | 内网 IP（别名） | `http://0x7f000001` | 拒绝请求 | P1 |
| SEC-URL-03 | 内网服务 | `http://169.254.169.254`（元数据） | 拒绝请求 | P0 |
| SEC-URL-04 | file:// 协议 | `file:///etc/passwd` | 拒绝请求 | P0 |
| SEC-URL-05 | 重定向到内网 | 外部 URL 302 → 127.0.0.1 | 中断或拒绝 | P1 |
| SEC-URL-06 | URL 为空 | `""` | 返回 422 | P1 |
| SEC-URL-07 | URL 格式非法 | `"not-a-url"` | 返回 422 | P1 |

### 2.4 API 访问控制

| 编号 | 测试用例 | 输入 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SEC-API-01 | CORS 跨域检查 | `OPTIONS /api/health` 带 Origin | 返回允许的 CORS 头 | P1 |
| SEC-API-02 | 不存在的路由 | `GET /api/nonexistent` | 返回 404，不泄露栈信息 | P1 |
| SEC-API-03 | 方法不允许 | `PUT /api/health` | 返回 405 | P2 |
| SEC-API-04 | 非对话 ID 格式 | `GET /api/conversations/not-a-number` | 返回 422 或 404 | P2 |

### 2.5 敏感信息泄露

| 编号 | 测试用例 | 输入 | 预期结果 | 优先级 |
|------|---------|------|---------|--------|
| SEC-LEAK-01 | 错误信息含堆栈 | 触发 500 | 返回通用错误，不暴露 `/src/` 路径 | P0 |
| SEC-LEAK-02 | API Key 在响应中 | 任意请求 | 不泄露任何 API Key | P0 |
| SEC-LEAK-03 | 调试信息在生产环境 | 任意请求 | 非 debug 模式不暴露内部状态 | P1 |
| SEC-LEAK-04 | 日志不记录敏感数据 | 发送含 Key 的问题 | 日志不明文记录 | P2 |

### 2.6 依赖安全

| 编号 | 检查项 | 方法 | 优先级 |
|------|--------|------|--------|
| SEC-DEP-01 | 已知漏洞扫描 | `pip audit` 或 `safety check` | P1 |
| SEC-DEP-02 | 前端依赖审计 | `npm audit` | P1 |
| SEC-DEP-03 | 过时依赖检测 | 定期 `pip list --outdated` | P2 |

---

## 3. 安全测试工具

### 3.1 自动化安全扫描

```bash
# Python 依赖安全审计
pip install pip-audit
pip-audit

# 前端依赖安全审计
cd frontend && npm audit

# 基本安全头检查
curl -s -I http://localhost:8000/api/health | grep -i "x-content-type-options"
```

### 3.2 手动安全测试

```bash
# XSS 测试
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"<script>alert(1)</script>"}'
```

---

## 4. 通过标准

- 所有 P0 安全用例 100% 通过
- 无 API Key / 内网地址 / 文件路径泄露
- 所有错误响应不含 Python 堆栈跟踪
- `npm audit` 无 critical 级别漏洞
