#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================="
echo "  KnowBase 质量门禁脚本"
echo "=========================================="
echo ""

run_step() {
    local name="$1"
    local cmd="$2"

    echo "------------------------------------------"
    echo "  $name"
    echo "------------------------------------------"
    (
        cd "$ROOT_DIR"
        eval "$cmd"
    )
    echo ""
}

run_step "后端 pytest" "uv run pytest backend/tests --tb=short -q"
run_step "前端单元测试" "cd frontend && npm test"
run_step "前端构建" "cd frontend && npm run build"
run_step "前端 API 类型漂移检查" "cd frontend && npm run check-api-types"

echo "全部质量门禁通过。"
