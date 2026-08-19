"""Daily provider request, response and error logs for local debugging."""

from __future__ import annotations

import json
import re
import shutil
import sys
import threading
import traceback
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.paths import DEFAULT_RUNTIME_DIR, PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / ".cache" / "pytest" / "logs" if "pytest" in sys.modules else DEFAULT_RUNTIME_DIR / "logs"
LOG_REQUEST_NAME = "request.log"
LOG_RESPONSE_NAME = "response.log"
LOG_ERROR_NAME = "error.log"

_retention_days = 30
_DIRECTORY_LOCK = threading.Lock()
_WRITE_LOCK = threading.Lock()
_SECRET_PATTERN = re.compile(
    r"(?ix)"
    r"(bearer\s+|api[_-]?key[=:]\s*)([^\s,;]+)"
    r"|(\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-[A-Za-z0-9-]{12,})\b)"
)
_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "key",
    "password",
    "secret",
    "token",
}


def configure_provider_logging(log_dir: Path, *, retention_days: int = 30) -> None:
    """Configure the provider log root before the server starts."""

    global LOG_DIR, _retention_days
    LOG_DIR = log_dir.expanduser().resolve()
    _retention_days = max(1, retention_days)


def log_api_request_sent(
    *,
    call_type: str,
    provider: str,
    url: str,
    request_body: Mapping[str, Any] | None,
    **metadata: Any,
) -> str:
    """Persist one provider request and return its correlation ID."""

    call_id = uuid4().hex
    _write_entry(
        LOG_REQUEST_NAME,
        {
            "type": _normalize_call_type(call_type),
            "provider": provider,
            "call_id": call_id,
            "url": _safe_url(url),
            "request": _redact(request_body or {}),
            **_redact(metadata),
        },
    )
    return call_id


def log_api_request_received(
    *,
    call_id: str,
    call_type: str,
    provider: str,
    url: str,
    response_body: Any,
    status_code: int,
    duration_ms: float,
    **metadata: Any,
) -> None:
    """Persist one provider response correlated with its request."""

    _write_entry(
        LOG_RESPONSE_NAME,
        {
            "type": _normalize_call_type(call_type),
            "provider": provider,
            "call_id": call_id,
            "url": _safe_url(url),
            "status_code": status_code,
            "duration_ms": round(duration_ms, 1),
            "response": _redact(response_body),
            **_redact(metadata),
        },
    )


def log_error(context: str, error: Exception | str, **metadata: Any) -> None:
    """Persist an error with a redacted traceback and safe metadata."""

    trace = None
    if isinstance(error, Exception):
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    _write_entry(
        LOG_ERROR_NAME,
        {
            "context": context,
            "error": _redact_text(str(error)),
            "traceback": _redact_text(trace) if trace else None,
            **_redact(metadata),
        },
    )


def _write_entry(filename: str, entry: Mapping[str, Any]) -> None:
    now = datetime.now().astimezone()
    line = f"{now.strftime('%Y-%m-%d %H:%M:%S%z')} {json.dumps(entry, ensure_ascii=False, default=str)}\n"
    path = _daily_log_path(now, filename)
    with _WRITE_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _daily_log_path(now: datetime, filename: str) -> Path:
    daily_dir = LOG_DIR / now.strftime("%Y-%m-%d")
    if not daily_dir.exists():
        with _DIRECTORY_LOCK:
            if not daily_dir.exists():
                daily_dir.mkdir(parents=True, exist_ok=True)
                _remove_expired_daily_logs(_retention_days)
    return daily_dir / filename


def _remove_expired_daily_logs(retention_days: int) -> None:
    dated_dirs: list[Path] = []
    for path in LOG_DIR.iterdir():
        if not path.is_dir() or path.is_symlink():
            continue
        try:
            parsed = date.fromisoformat(path.name)
        except ValueError:
            continue
        if parsed.isoformat() == path.name:
            dated_dirs.append(path)
    for expired in sorted(dated_dirs, key=lambda path: path.name, reverse=True)[retention_days:]:
        try:
            shutil.rmtree(expired)
        except OSError:
            continue


def _normalize_call_type(value: str) -> str:
    return value.strip().lower().replace("-", "_") or "provider_call"


def _safe_url(value: str) -> str:
    return value.partition("?")[0]


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): "***REDACTED***" if str(key).lower() in _SECRET_KEYS else _redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    return _SECRET_PATTERN.sub(lambda match: f"{match.group(1) or ''}***REDACTED***", value)


__all__ = [
    "LOG_DIR",
    "LOG_ERROR_NAME",
    "LOG_REQUEST_NAME",
    "LOG_RESPONSE_NAME",
    "configure_provider_logging",
    "log_api_request_received",
    "log_api_request_sent",
    "log_error",
]
