#!/usr/bin/env bash
# KnowBase 开发环境启动脚本
# 同时启动 FastAPI 后端 (8000) 和 React 前端 (5173)
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      echo "🧹 清理端口 $port 上的旧进程: $pids"
      kill $pids 2>/dev/null || true
      sleep 1
    fi
  elif command -v fuser >/dev/null 2>&1; then
    if fuser "$port"/tcp >/dev/null 2>&1; then
      echo "🧹 清理端口 $port 上的旧进程"
      fuser -k "$port"/tcp 2>/dev/null || true
      sleep 1
    fi
  fi
}

cleanup() {
  echo ""
  echo "正在关闭服务..."
  [ -n "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null
  echo "服务已关闭"
}
trap cleanup EXIT INT TERM

kill_port 8000
kill_port 5173

# 后端先同步依赖再启动
echo "🚀 启动 FastAPI 后端 (端口 8000)..."
cd "$ROOT/backend"
uv sync 2>/dev/null
uv run uvicorn src.api.main:app --reload --port 8000 --host 0.0.0.0 &
BACKEND_PID=$!

# 等待后端就绪
echo "⏳ 等待后端就绪..."
for i in $(seq 1 60); do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ 后端就绪"
    break
  fi
  if [ $i -eq 60 ]; then
    echo "❌ 后端启动超时（首次运行需下载 chromadb 等大包，请耐心等待）"
    exit 1
  fi
  sleep 2
done

# 启动前端
echo "🚀 启动 React 前端 (端口 5173)..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "═══════════════════════════════════════════"
echo "  KnowBase 开发环境已启动"
echo "  后端 API:  http://localhost:8000"
echo "  前端界面:  http://localhost:5173"
echo "  API 文档:  http://localhost:8000/docs"
echo "═══════════════════════════════════════════"
echo "按 Ctrl+C 停止所有服务"

wait
