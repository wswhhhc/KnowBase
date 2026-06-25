@echo off
chcp 65001 >nul
cd /d "%~dp0.."

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

:: 后端先安装依赖再启动
echo [1/2] 启动 FastAPI 后端 (端口 8000)...
start "KnowBase-Backend" cmd /c "cd /d "%~dp0..\backend" && uv sync && uv run uvicorn src.api.main:app --reload --port 8000 --host 0.0.0.0"

:: 等几秒让后端先启动
echo 等待后端就绪...
timeout /t 8 /nobreak >nul

:: 启动前端
echo [2/2] 启动 React 前端 (端口 5173)...
start "KnowBase-Frontend" cmd /c "cd /d "%~dp0..\frontend" && npm run dev"

echo.
echo ===========================================
echo   后端 API:  http://localhost:8000
echo   前端界面:  http://localhost:5173
echo   API 文档:  http://localhost:8000/docs
echo ===========================================
echo.
echo 关闭所有窗口即可停止服务。
pause
