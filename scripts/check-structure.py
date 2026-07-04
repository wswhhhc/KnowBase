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


def main() -> int:
    violations = [
        *_check_forbidden_imports(),
        *_check_pages_are_real_containers(),
        *_check_component_page_shells(),
        *_check_active_docs_do_not_reference_legacy_paths(),
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
