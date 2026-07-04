#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

resolve_windows_command() {
    local name="$1"
    local win_path

    if ! command -v cmd.exe >/dev/null 2>&1; then
        return 1
    fi

    win_path="$(cmd.exe /c "where $name" 2>/dev/null | head -n 1 | tr -d '\r')"
    if [[ -z "$win_path" ]]; then
        return 1
    fi

    if command -v wslpath >/dev/null 2>&1; then
        wslpath "$win_path"
    else
        printf '%s\n' "$win_path"
    fi
}

resolve_command() {
    local primary="$1"
    shift
    local candidate

    candidate="$(command -v "$primary" 2>/dev/null || true)"
    if [[ -n "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    for fallback in "$@"; do
        candidate="$(resolve_windows_command "$fallback" || true)"
        if [[ -n "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
}

PYTHON_BIN="$(resolve_command python python py)"
UV_BIN="$(resolve_command uv uv)"
NPM_BIN="$(resolve_command npm npm.cmd npm)"

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

run_step "后端 pytest" "cd backend && \"$UV_BIN\" run pytest tests --tb=short -q"
run_step "结构守卫" "\"$PYTHON_BIN\" scripts/check-structure.py"
run_step "前端单元测试" "cd frontend && \"$NPM_BIN\" test"
run_step "前端构建" "cd frontend && \"$NPM_BIN\" run build"
run_step "前端 API 类型漂移检查" "cd frontend && \"$NPM_BIN\" run check-api-types"

echo "全部质量门禁通过。"
