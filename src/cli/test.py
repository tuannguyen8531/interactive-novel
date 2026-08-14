"""Run the standard Python validation pipeline."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _clean_output(stdout: str, stderr: str) -> str:
    """Remove terminal color codes before printing command output."""
    return ANSI_ESCAPE.sub("", "\n".join(part.strip() for part in (stdout, stderr) if part.strip()))


def _run(label: str, command: list[str], project_root: Path) -> bool:
    result = subprocess.run(command, cwd=project_root, capture_output=True, text=True, check=False)
    output = _clean_output(result.stdout, result.stderr)
    if result.returncode == 0:
        print(f"PASS {label}")
        return True
    print(f"FAIL {label} (exit {result.returncode})")
    if output:
        print(output)
    return False


def main(argv: list[str] | None = None) -> int:
    """Run Ruff, Pyright and Pytest with one project command."""
    parser = argparse.ArgumentParser(prog="interactive-novel test")
    parser.add_argument("--fix", action="store_true", help="Apply safe Ruff fixes and formatting.")
    parser.add_argument("--no-lint", action="store_true", help="Skip Ruff lint.")
    parser.add_argument("--no-format", action="store_true", help="Skip Ruff format.")
    parser.add_argument("--no-pyright", action="store_true", help="Skip Pyright.")
    parser.add_argument("--no-pytest", action="store_true", help="Skip Pytest.")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[2]
    commands: list[tuple[str, list[str]]] = []
    if not args.no_lint:
        lint = [sys.executable, "-m", "ruff", "check", "."]
        if args.fix:
            lint.insert(-1, "--fix")
        commands.append(("ruff check", lint))
    if not args.no_format:
        format_args = ["--quiet"] if args.fix else ["--check"]
        commands.append(("ruff format", [sys.executable, "-m", "ruff", "format", *format_args, "."]))
    if not args.no_pyright:
        commands.append(("pyright", [sys.executable, "-m", "pyright"]))
    if not args.no_pytest:
        extra = args.pytest_args[1:] if args.pytest_args[:1] == ["--"] else args.pytest_args
        commands.append(("pytest", [sys.executable, "-m", "pytest", "tests", "-q", *extra]))

    results = [_run(label, command, project_root) for label, command in commands]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
