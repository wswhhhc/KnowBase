# Contributing

本仓库后端使用 `uv` 管理 Python 依赖，前端使用 `npm`。提交前请保持改动范围清晰，并在行为、接口或启动方式变化时同步更新文档。

## 开发环境

### 前置要求

- Python 3.11+
- Node.js 20+
- `uv`

### 初始化

```bash
git clone <repo-url>
cd KnowBase

cp backend/.env.example backend/.env

cd backend
uv sync

cd ../frontend
npm install
```

Windows PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env
```

## 本地运行

优先使用仓库根目录下的辅助脚本：

```bash
bash scripts/dev.sh
```

Windows PowerShell:

```powershell
scripts\dev.bat
```

也可以分别启动：

```bash
cd backend
uv run uvicorn src.api.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

## 测试要求

至少运行覆盖你改动范围的测试。

### 后端

```bash
cd backend
uv run python -m unittest discover -v
```

### 前端

```bash
cd frontend
npm test
```

### 全量本地检查

```bash
bash scripts/run-tests.sh
```

## 协作规则

- 后端接口变化后，要同步更新前端生成的 API 类型。
- 启动方式、配置项、产品行为或架构假设变化后，要同步更新 `README.md`、`docs/requirements.md` 或相关文档。
- 不要提交密钥、本地数据库、覆盖率产物或运行期生成文件。
- 尽量保持 PR 小而明确，一个 PR 解决一个清晰问题。

## API 类型更新

如果 `backend/openapi.json` 发生变化，重新生成前端类型：

```bash
cd frontend
npm run gen-api-types
```

## 提交前检查

- 改动目标和原因清晰。
- 相关前后端测试已在本地通过。
- 如果接口、行为或配置变更，文档已同步更新。
- 新增配置项已经体现在 `backend/.env.example`。
