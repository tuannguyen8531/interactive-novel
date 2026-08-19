from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from src.cli import serve as serve_cli
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


def test_serve_prints_clickable_url_before_starting_uvicorn(monkeypatch, capsys) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    logging_calls: list[tuple[Path, int]] = []
    monkeypatch.setattr(
        serve_cli,
        "get_settings",
        lambda: SimpleNamespace(
            api_host="0.0.0.0",
            api_port=8123,
            api_log_level="info",
            runtime_dir=Path("runtime"),
            log_retention_days=14,
        ),
    )
    monkeypatch.setattr(
        serve_cli,
        "configure_provider_logging",
        lambda path, *, retention_days: logging_calls.append((path, retention_days)),
    )
    monkeypatch.setattr(serve_cli.uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))

    assert serve_cli.main() == 0

    assert capsys.readouterr().out == "Starting service at http://127.0.0.1:8123\n"
    assert logging_calls == [(Path(__file__).resolve().parents[2] / "runtime" / "logs", 14)]
    assert calls == [
        (
            "src.api.factory:create_app",
            {
                "factory": True,
                "host": "0.0.0.0",
                "port": 8123,
                "log_level": "info",
            },
        )
    ]
