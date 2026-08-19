from __future__ import annotations

import subprocess
from pathlib import Path

from src.cli import test as test_cli


def test_frontend_flag_runs_vue_unit_tests_from_web_directory(monkeypatch) -> None:
    commands: list[tuple[list[str], Path]] = []

    def fake_run(command, *, cwd, **kwargs):
        del kwargs
        commands.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, stdout="10 passed", stderr="")

    monkeypatch.setattr(test_cli.shutil, "which", lambda _: "/usr/bin/npm")
    monkeypatch.setattr(test_cli.subprocess, "run", fake_run)

    result = test_cli.main(["--no-lint", "--no-format", "--no-pyright", "--no-pytest", "--frontend"])

    assert result == 0
    assert commands == [
        (["/usr/bin/npm", "run", "test:unit"], Path(__file__).resolve().parents[2] / "web"),
    ]
