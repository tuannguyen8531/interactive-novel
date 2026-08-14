from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src"


def _module(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names if alias.name.startswith("src"))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src"):
            imported.add(node.module)
    return imported


def _python_modules() -> dict[str, Path]:
    return {_module(path): path for path in SOURCE_ROOT.rglob("*.py")}


def test_backend_dependency_direction() -> None:
    violations: list[str] = []
    for owner, path in _python_modules().items():
        for target in _imports(path):
            if owner.startswith("src.domain.") and not target.startswith("src.domain"):
                violations.append(f"{owner} -> {target}: domain must remain independent")
            if owner.startswith("src.services.") and target.startswith(("src.application", "src.api", "src.cli", "src.graph")):
                violations.append(f"{owner} -> {target}: infrastructure cannot depend on upper layers")
            if owner.startswith("src.application.") and target.startswith(("src.api", "src.cli")):
                violations.append(f"{owner} -> {target}: application cannot depend on adapters")
            if owner.startswith("src.graph.") and target.startswith(("src.application", "src.api", "src.cli")):
                violations.append(f"{owner} -> {target}: graph cannot depend on adapters or use cases")
    assert not violations, "\n".join(violations)


def test_backend_import_graph_has_no_cycles() -> None:
    modules = _python_modules()
    graph: dict[str, set[str]] = defaultdict(set)
    for owner, path in modules.items():
        for target in _imports(path):
            if target in modules and target != owner:
                graph[owner].add(target)

    visiting: list[str] = []
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            start = visiting.index(module)
            cycle = " -> ".join([*visiting[start:], module])
            raise AssertionError(f"Import cycle: {cycle}")
        if module in visited:
            return
        visiting.append(module)
        for dependency in graph[module]:
            visit(dependency)
        visiting.pop()
        visited.add(module)

    for module in modules:
        visit(module)


def test_skeleton_has_expected_boundaries() -> None:
    for relative in (
        "src/api/factory.py",
        "src/api/routes/health.py",
        "src/application/errors.py",
        "src/cli/serve.py",
        "src/graph/__init__.py",
        "src/domain/__init__.py",
        "src/services/__init__.py",
    ):
        assert (ROOT / relative).is_file(), relative
