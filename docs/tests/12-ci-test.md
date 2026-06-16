# CI 测试文档

## 1. 概述

**目标**: 定义 KnowBase 的持续集成流程，确保每次代码提交自动运行测试和覆盖率检查。

**技术栈**: GitHub Actions

**触发器**: `push` 和 `pull_request` 到任意分支

---

## 2. Workflow 定义

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, '**']
  pull_request:
    branches: [main]

jobs:
  backend:
    name: Backend Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: cd backend && uv sync

      - name: Run tests
        run: cd backend && uv run python -m unittest discover -v

  frontend:
    name: Frontend Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run tests
        run: cd frontend && npm test
```

---

## 3. CI 阶段说明

### 3.1 Backend job

| 步骤 | 说明 | 预期时间 |
|------|------|---------|
| Checkout | 拉取代码 | < 10s |
| Setup Python | 安装 Python 3.12 | < 30s |
| Install uv | 安装 uv 包管理器 | < 10s |
| uv sync | 安装依赖 | < 60s |
| Run tests | 执行 unittest discover | < 30s |

### 3.2 Frontend job

| 步骤 | 说明 | 预期时间 |
|------|------|---------|
| Checkout | 拉取代码 | < 10s |
| Setup Node | 安装 Node.js 20 | < 20s |
| npm ci | 安装依赖（使用缓存） | < 60s |
| Run tests | 执行 vitest | < 30s |

---

## 4. 质量门禁

| 检查项 | 要求 | 阻断合并 |
|--------|------|---------|
| 后端测试通过率 | 100% | 是 |
| 前端测试通过率 | 100% | 是 |
| 后端覆盖率达到基线 | >= 80% | 建议 |
| 前端覆盖率达到基线 | >= 60% | 建议 |

---

## 5. 本地模拟 CI

```bash
# 在提交前本地运行全部测试
cd backend && uv run python -m unittest discover -v
cd frontend && npm test
```

---

## 6. 通过标准

- CI 流程正常触发并完成
- 后端和前端 job 均通过
- 总运行时间 < 3 分钟
- push 和 pull_request 均触发
