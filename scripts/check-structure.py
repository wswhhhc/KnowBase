#!/usr/bin/env python3
"""Guard against structural regressions after the remediation work."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _iter_files(base: Path, pattern: str) -> list[Path]:
    return sorted(path for path in base.rglob(pattern) if path.is_file())


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_forbidden_imports() -> list[str]:
    violations: list[str] = []

    backend_patterns = [
        (re.compile(r"\b(?:from|import)\s+src\.conversations\b"), "禁止在源代码中继续依赖 src.conversations"),
        (re.compile(r"\b(?:from|import)\s+src\.graph\.nodes\b"), "禁止在源代码中继续把 src.graph.nodes 当主入口"),
    ]
    backend_excludes: set[Path] = set()

    for path in _iter_files(ROOT / "backend" / "src", "*.py"):
        if path in backend_excludes:
            continue
        source = _read(path)
        for pattern, message in backend_patterns:
            if pattern.search(source):
                violations.append(f"{message}: {path.relative_to(ROOT)}")

    frontend_pattern = re.compile(r"(['\"])(?:@/|\.{1,2}/.*)?lib/api-types(?:\.openapi)?\1")
    for path in _iter_files(ROOT / "frontend" / "src", "*.ts") + _iter_files(ROOT / "frontend" / "src", "*.tsx"):
        if frontend_pattern.search(_read(path)):
            violations.append(f"禁止继续依赖 frontend/src/lib/api-types*: {path.relative_to(ROOT)}")

    frontend_api_pattern = re.compile(r"(['\"])(?:@/|\.{1,2}/.*)?lib/api\1")
    for path in _iter_files(ROOT / "frontend" / "src", "*.ts") + _iter_files(ROOT / "frontend" / "src", "*.tsx"):
        if frontend_api_pattern.search(_read(path)):
            violations.append(f"禁止继续依赖 frontend/src/lib/api: {path.relative_to(ROOT)}")

    return violations


def _check_pages_are_real_containers() -> list[str]:
    violations: list[str] = []
    shell_re = re.compile(r"^\s*export\s+(?:\{\s*default\s*\}\s+from|\*\s+from)\s+['\"].+['\"]\s*;?\s*$")

    for path in _iter_files(ROOT / "frontend" / "src" / "pages", "*.tsx"):
        source = _read(path).strip()
        if shell_re.fullmatch(source):
            violations.append(f"pages 层不能继续只是 re-export 壳: {path.relative_to(ROOT)}")

    return violations


def _check_component_page_shells() -> list[str]:
    violations: list[str] = []
    shell_re = re.compile(r"^\s*export\s+(?:\{\s*default\s*\}\s+from|\*\s+from)\s+['\"]@/pages/.+['\"]\s*;?\s*$")

    candidate_paths = [
        *_iter_files(ROOT / "frontend" / "src" / "components", "*Page.tsx"),
        ROOT / "frontend" / "src" / "components" / "ChatArea.tsx",
    ]

    for path in candidate_paths:
        if not path.is_file():
            continue
        source = _read(path).strip()
        if shell_re.fullmatch(source):
            violations.append(f"旧页面组件壳必须退场: {path.relative_to(ROOT)}")

    return violations


def _document_route_boundary_violations(source: str) -> list[str]:
    boundary_patterns = [
        (re.compile(r"\basyncio\.sleep\s*\("), "Documents 路由不能重新实现任务轮询"),
        (re.compile(r"\baudit_store\.record_event\s*\("), "Documents 路由不能直接拼装审计事件"),
        (re.compile(r"src\.jobs\.document_tasks:"), "Documents 路由不能直接拼装后台任务 target path"),
        (re.compile(r"\bgenerate_suggested_questions\s*\("), "Documents 路由不能直接收集推荐问题"),
        (re.compile(r"\bEventSourceResponse\s*\("), "Documents 路由不能直接创建任务 SSE 响应"),
        (re.compile(r"\bjob_store\.get_job\s*\("), "Documents 路由不能直接读取任务状态"),
        (re.compile(r"\benqueue_tracked_job\s*\("), "Documents 路由不能直接编排后台任务"),
    ]
    return [message for pattern, message in boundary_patterns if pattern.search(source)]


def _check_documents_route_boundaries() -> list[str]:
    route_path = ROOT / "backend" / "src" / "api" / "routes" / "documents.py"
    return [
        f"{message}: {route_path.relative_to(ROOT)}"
        for message in _document_route_boundary_violations(_read(route_path))
    ]


def _service_boundary_violations(source: str) -> list[str]:
    boundary_patterns = [
        (
            re.compile(
                r"^\s*(?:from\s+fastapi(?:\.[A-Za-z_]\w*)*\s+import\s+|import\s+fastapi(?:\.[A-Za-z_]\w*)*\b)",
                re.MULTILINE,
            ),
            "应用服务不能依赖 FastAPI",
        ),
        (
            re.compile(
                r"^\s*(?:from\s+src\.api\.models\s+import\s+|import\s+src\.api\.models\b)",
                re.MULTILINE,
            ),
            "应用服务不能依赖 src.api.models",
        ),
        (
            re.compile(
                r"^\s*(?:from\s+sse_starlette(?:\.[A-Za-z_]\w*)*\s+import\s+|import\s+sse_starlette(?:\.[A-Za-z_]\w*)*\b)",
                re.MULTILINE,
            ),
            "应用服务不能依赖 SSE 响应类型",
        ),
    ]
    return [message for pattern, message in boundary_patterns if pattern.search(source)]


def _check_service_boundaries() -> list[str]:
    violations: list[str] = []
    for path in _iter_files(ROOT / "backend" / "src" / "services", "*.py"):
        for message in _service_boundary_violations(_read(path)):
            violations.append(f"{message}: {path.relative_to(ROOT)}")
    return violations


def _document_panel_boundary_violations(source: str) -> list[str]:
    runtime_api_import = re.compile(
        r"^\s*import\s+(?!type\b)(?P<clause>"
        r"[A-Za-z_$][\w$]*(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+[A-Za-z_$][\w$]*))?"
        r"|\{[^}]*\}|\*\s+as\s+[A-Za-z_$][\w$]*"
        r")\s+from\s+['\"]@/shared/api(?:/[^'\"]+)?['\"]",
        re.MULTILINE,
    )
    side_effect_api_import = re.compile(
        r"^\s*import\s+['\"]@/shared/api(?:/[^'\"]+)?['\"]",
        re.MULTILINE,
    )
    for match in runtime_api_import.finditer(source):
        clause = match.group("clause").strip()
        if clause.startswith("{") and clause.endswith("}"):
            specifiers = [specifier.strip() for specifier in clause[1:-1].split(",") if specifier.strip()]
            if specifiers and all(specifier.startswith("type ") for specifier in specifiers):
                continue
        return ["DocumentPanel 不能直接依赖运行时 API client"]
    if side_effect_api_import.search(source):
        return ["DocumentPanel 不能直接依赖运行时 API client"]
    return []


def _check_document_panel_boundaries() -> list[str]:
    panel_path = ROOT / "frontend" / "src" / "components" / "sidebar" / "DocumentPanel.tsx"
    return [
        f"{message}: {panel_path.relative_to(ROOT)}"
        for message in _document_panel_boundary_violations(_read(panel_path))
    ]


def _chat_page_preference_violations(source: str) -> list[str]:
    preference_key = re.compile(r"['\"]kb_(?:web_search|search_strategy)['\"]")
    local_storage_access = re.compile(r"\blocalStorage\.(?:getItem|setItem)\s*\(")
    if preference_key.search(source) and local_storage_access.search(source):
        return ["ChatPage 不能直接读写搜索偏好 localStorage"]
    return []


def _check_chat_page_preference_boundaries() -> list[str]:
    page_path = ROOT / "frontend" / "src" / "pages" / "chat" / "ChatPage.tsx"
    return [
        f"{message}: {page_path.relative_to(ROOT)}"
        for message in _chat_page_preference_violations(_read(page_path))
    ]


def _check_active_docs_do_not_reference_legacy_paths() -> list[str]:
    violations: list[str] = []
    legacy_patterns = [
        (re.compile(r"\blib/api\.ts\b"), "文档不应继续把 lib/api.ts 作为当前结构事实来源"),
        (re.compile(r"\blib/api-types(?:\.openapi)?\.ts\b"), "文档不应继续引用旧的 lib/api-types* 路径"),
    ]
    doc_paths = [
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        *_iter_files(ROOT / "docs" / "testing", "*.md"),
    ]

    for path in doc_paths:
        if not path.is_file():
            continue
        source = _read(path)
        for pattern, message in legacy_patterns:
            if pattern.search(source):
                violations.append(f"{message}: {path.relative_to(ROOT)}")

    return violations


def _check_compose_uses_production_commands() -> list[str]:
    violations: list[str] = []
    compose_path = ROOT / "docker-compose.yml"
    backend_dockerfile = ROOT / "docker" / "Dockerfile.backend"
    frontend_dockerfile = ROOT / "docker" / "Dockerfile.frontend"

    compose = _read(compose_path)
    backend = _read(backend_dockerfile)
    frontend = _read(frontend_dockerfile)

    forbidden = [
        ("--reload", "准生产 Compose/Dockerfile 不能启用后端热重载"),
        ("npm run dev", "准生产 Compose/Dockerfile 不能启动 Vite dev server"),
        ("./backend:/app/backend", "准生产 Compose 不应挂载 backend 源码覆盖镜像"),
        ("./frontend:/app/frontend", "准生产 Compose 不应挂载 frontend 源码覆盖镜像"),
    ]
    combined = {
        compose_path: compose,
        backend_dockerfile: backend,
        frontend_dockerfile: frontend,
    }
    for path, source in combined.items():
        for marker, message in forbidden:
            if marker in source:
                violations.append(f"{message}: {path.relative_to(ROOT)}")

    if "preview" not in frontend:
        violations.append("frontend 镜像应运行已构建产物: docker/Dockerfile.frontend")
    if "RUN npm run build" not in frontend:
        violations.append("frontend 镜像应在构建阶段执行 npm run build: docker/Dockerfile.frontend")

    return violations


def main() -> int:
    violations = [
        *_check_forbidden_imports(),
        *_check_documents_route_boundaries(),
        *_check_service_boundaries(),
        *_check_document_panel_boundaries(),
        *_check_chat_page_preference_boundaries(),
        *_check_pages_are_real_containers(),
        *_check_component_page_shells(),
        *_check_active_docs_do_not_reference_legacy_paths(),
        *_check_compose_uses_production_commands(),
    ]
    if not violations:
        print("结构守卫通过。")
        return 0

    print("发现结构回退：", file=sys.stderr)
    for violation in violations:
        print(f"- {violation}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
