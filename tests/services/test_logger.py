from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from src.services import logger


def _entry(path: Path) -> dict[str, object]:
    line = path.read_text(encoding="utf-8").strip()
    return json.loads(line[line.index("{") :])


def test_provider_logs_keep_payloads_correlated_and_redact_secrets(tmp_path, monkeypatch) -> None:
    log_root = tmp_path / "logs"
    monkeypatch.setattr(logger, "LOG_DIR", log_root)
    monkeypatch.setattr(logger, "_retention_days", 30)

    call_id = logger.log_api_request_sent(
        call_type="world-builder",
        provider="openrouter",
        url="https://provider.test/chat?key=secret-query",
        request_body={
            "messages": [{"content": "A full story prompt"}],
            "api_key": "sk-this-must-not-appear",
        },
        authorization="Bearer sk-another-secret-value",
        model="fixture-model",
    )
    logger.log_api_request_received(
        call_id=call_id,
        call_type="world-builder",
        provider="openrouter",
        url="https://provider.test/chat?key=secret-query",
        response_body={"choices": [{"message": {"content": "The full model output"}}]},
        status_code=200,
        duration_ms=12.34,
        model="fixture-model",
    )
    logger.log_error(
        "Provider failed",
        RuntimeError("authorization: Bearer sk-this-is-also-secret"),
        call_id=call_id,
    )

    daily = log_root / date.today().isoformat()
    request = _entry(daily / logger.LOG_REQUEST_NAME)
    response = _entry(daily / logger.LOG_RESPONSE_NAME)
    error = _entry(daily / logger.LOG_ERROR_NAME)

    assert request["call_id"] == response["call_id"] == error["call_id"] == call_id
    assert request["type"] == "world_builder"
    assert request["url"] == "https://provider.test/chat"
    assert "A full story prompt" in json.dumps(request)
    assert "The full model output" in json.dumps(response)
    combined = json.dumps([request, response, error])
    assert "secret-query" not in combined
    assert "sk-this-must-not-appear" not in combined
    assert "sk-another-secret-value" not in combined
    assert "sk-this-is-also-secret" not in combined


def test_provider_log_retention_removes_oldest_daily_directories(tmp_path, monkeypatch) -> None:
    log_root = tmp_path / "logs"
    monkeypatch.setattr(logger, "LOG_DIR", log_root)
    monkeypatch.setattr(logger, "_retention_days", 2)
    log_root.mkdir()
    old_days = [date.today() - timedelta(days=offset) for offset in (3, 2, 1)]
    for day in old_days:
        (log_root / day.isoformat()).mkdir()

    logger.log_error("Latest error", "fixture")

    remaining = sorted(path.name for path in log_root.iterdir() if path.is_dir())
    assert remaining == sorted([old_days[-1].isoformat(), date.today().isoformat()])
