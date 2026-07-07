@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if /I "%~1"=="--docker" (
  if not exist ".env.compose" (
    echo 缺少 .env.compose。请先复制 .env.compose.example 为 .env.compose，并填写必填密钥。
    exit /b 1
  )
  docker compose --env-file .env.compose up --build
  goto :eof
)

echo ===========================================
echo   KnowBase 开发环境启动
echo ===========================================
echo.

echo 清理旧的开发服务端口...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 8000,5173; " ^
  "foreach ($port in $ports) { " ^
  "  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | " ^
  "    Select-Object -ExpandProperty OwningProcess -Unique | " ^
  "    ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop; Write-Host ('已停止占用端口 ' + $port + ' 的进程 PID=' + $_) } catch {} } " ^
  "}"
echo.

:: 后端先安装依赖
echo [1/4] 同步后端依赖...
pushd "%~dp0..\backend"
uv sync
popd

:: 本地开发没有 Redis 时启动项目内置 fake Redis
echo [2/4] 检查 Redis/RQ 后台任务依赖...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (-not (Get-NetTCPConnection -LocalPort 6379 -State Listen -ErrorAction SilentlyContinue)) { exit 1 }"
if errorlevel 1 (
  echo 未检测到 6379 Redis，启动本地 fake Redis...
  start "KnowBase-Redis" cmd /c "cd /d "%~dp0..\backend" && set "PLAYWRIGHT_REDIS_PORT=6379" && uv run python scripts/start_fake_redis.py"
  timeout /t 2 /nobreak >nul
) else (
  echo 已检测到 Redis 监听 6379，复用现有 Redis。
)

echo 启动 RQ worker...
start "KnowBase-Worker" cmd /c "cd /d "%~dp0..\backend" && uv run python -m src.jobs.worker"

:: 启动后端
echo [3/4] 启动 FastAPI 后端 (端口 8000)...
start "KnowBase-Backend" cmd /c "cd /d "%~dp0..\backend" && uv sync && uv run uvicorn src.api.main:app --reload --port 8000 --host 0.0.0.0"

:: 等几秒让后端先启动
echo 等待后端就绪...
timeout /t 8 /nobreak >nul

:: 启动前端
echo [4/4] 启动 React 前端 (端口 5173)...
start "KnowBase-Frontend" cmd /c "cd /d "%~dp0..\frontend" && npm run dev"

echo.
echo ===========================================
echo   后端 API:  http://localhost:8000
echo   前端界面:  http://localhost:5173
echo   API 文档:  http://localhost:8000/docs
echo   Redis/RQ:  redis://localhost:6379/0 / knowbase
echo ===========================================
echo.
echo 关闭所有窗口即可停止服务。
pause
