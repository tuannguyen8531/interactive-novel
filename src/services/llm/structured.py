"""Bounded JSON parsing and repair for provider structured responses."""

from __future__ import annotations

import json
import re
from typing import Any

from src.application.contracts.providers import StructuredOutputError, StructuredSchema

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _without_code_fence(text: str) -> str:
    value = text.strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _decode_json(value: str) -> Any:
    decoder = json.JSONDecoder()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        repaired = _TRAILING_COMMA.sub(r"\1", value)
        if repaired != value:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        for index, character in enumerate(value):
            if character not in "[{":
                continue
            try:
                payload, _ = decoder.raw_decode(value[index:])
                return payload
            except json.JSONDecodeError:
                continue
    raise ValueError("response did not contain a complete JSON value")


def parse_structured_text(text: str, schema: StructuredSchema, *, provider: str) -> Any:
    """Parse a JSON object/array, strip presentation fences, then validate it."""
    try:
        payload = _decode_json(_without_code_fence(text))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise StructuredOutputError(
            f"{provider} returned invalid JSON for schema {schema.name}.",
            provider=provider,
            fallback_eligible=True,
        ) from error
    return schema.validate(payload, provider=provider)


__all__ = ["parse_structured_text"]
