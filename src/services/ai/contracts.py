"""Parse provider output into versioned AI role contracts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, cast

from pydantic import ValidationError

from src.application.contracts.ai import (
    AIOutput,
    AIPromptRole,
    ConsistencyReport,
    CritiqueResult,
    NarrativeDraft,
    SimulationResult,
    TurnPlan,
    VersionedOutput,
    WorldSeed,
)
from src.application.contracts.providers import StructuredOutputError, StructuredSchema


class ContractDiagnostic:
    """Small serializable diagnostic returned without exposing raw model text."""

    __slots__ = ("path", "code", "message")

    def __init__(self, path: str, code: str, message: str) -> None:
        self.path = path
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}

    def __repr__(self) -> str:
        return f"ContractDiagnostic(path={self.path!r}, code={self.code!r}, message={self.message!r})"


class AIContractValidationError(ValueError):
    """Safe validation error with field-level diagnostics."""

    code = "ai_contract_validation_error"

    def __init__(self, role: AIPromptRole | str, diagnostics: tuple[ContractDiagnostic, ...]) -> None:
        self.role = str(role)
        self.diagnostics = diagnostics
        summary = "; ".join(f"{item.path}: {item.message}" for item in diagnostics)
        super().__init__(f"{self.role} contract validation failed: {summary}")


ROLE_MODELS: Mapping[AIPromptRole, type[VersionedOutput]] = {
    AIPromptRole.WORLD_BUILDER: WorldSeed,
    AIPromptRole.PLANNER: TurnPlan,
    AIPromptRole.SIMULATOR: SimulationResult,
    AIPromptRole.CONTEXT_VALIDATOR: ConsistencyReport,
    AIPromptRole.WRITER: NarrativeDraft,
    AIPromptRole.CRITIC: CritiqueResult,
}

_TRACE_FIELDS = (
    "schema_version",
    "role",
    "run_id",
    "prompt_version",
    "physical_call_id",
    "config_snapshot_id",
)


class AIContractRegistry:
    """Registry connecting logical roles to strict Pydantic output models."""

    def model_for(self, role: AIPromptRole | str) -> type[VersionedOutput]:
        normalized = AIPromptRole(role)
        try:
            return ROLE_MODELS[normalized]
        except KeyError as error:
            raise ValueError(f"No AI output contract registered for role {normalized.value}.") from error

    def parse(self, role: AIPromptRole | str, payload: Any) -> AIOutput:
        from .validators import validate_semantics

        normalized = AIPromptRole(role)
        model = self.model_for(normalized)
        payload = _normalize_role_payload(normalized, model, payload)
        try:
            result = model.model_validate(payload)
        except ValidationError as error:
            raise AIContractValidationError(normalized, _diagnostics(error)) from error
        if result.role != model.expected_role:
            diagnostic = ContractDiagnostic(
                "role",
                "role_mismatch",
                f"expected role {model.expected_role.value}, received {result.role.value}",
            )
            raise AIContractValidationError(normalized, (diagnostic,))
        if result.schema_version != model.expected_schema_version:
            diagnostic = ContractDiagnostic(
                "schema_version",
                "schema_version_mismatch",
                f"expected {model.expected_schema_version}, received {result.schema_version}",
            )
            raise AIContractValidationError(normalized, (diagnostic,))
        try:
            validate_semantics(result)
        except AIContractValidationError:
            raise
        except ValueError as error:
            diagnostic = ContractDiagnostic("$", "semantic_validation_error", str(error))
            raise AIContractValidationError(normalized, (diagnostic,)) from error
        return cast(AIOutput, result)

    def parse_json(self, role: AIPromptRole | str, text: str) -> AIOutput:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            normalized = AIPromptRole(role)
            diagnostic = ContractDiagnostic("$", "invalid_json", "response is not valid JSON")
            raise AIContractValidationError(normalized, (diagnostic,)) from error
        return self.parse(role, payload)

    def structured_schema(
        self,
        role: AIPromptRole | str,
        *,
        authoritative_metadata: Mapping[str, Any] | None = None,
    ) -> StructuredSchema:
        normalized = AIPromptRole(role)
        model = self.model_for(normalized)

        def validate(payload: Any) -> VersionedOutput:
            try:
                normalized_payload = _normalize_role_payload(normalized, model, payload)
                if isinstance(normalized_payload, Mapping) and authoritative_metadata:
                    normalized_payload = {
                        **normalized_payload,
                        **{
                            key: value
                            for key, value in authoritative_metadata.items()
                            if key in _TRACE_FIELDS and value is not None
                        },
                    }
                return self.parse(normalized, normalized_payload)
            except AIContractValidationError as error:
                raise StructuredOutputError(
                    f"{normalized.value} output failed its typed contract.",
                    provider="ai-contract",
                    fallback_eligible=True,
                ) from error

        return StructuredSchema(
            name=f"{normalized.value}_output",
            json_schema=model.model_json_schema(),
            validator=validate,
        )


def _normalize_role_payload(
    role: AIPromptRole,
    model: type[VersionedOutput],
    payload: Any,
) -> Any:
    """Unwrap a single, explicit role envelope emitted by some providers."""

    if not isinstance(payload, Mapping):
        return payload
    model_key = re.sub(r"(?<!^)(?=[A-Z])", "_", model.__name__).lower()
    allowed_envelope_keys = {*_TRACE_FIELDS, "metadata", role.value, model_key}
    if not set(payload).issubset(allowed_envelope_keys):
        return payload
    for wrapper_key in (model_key, role.value):
        nested = payload.get(wrapper_key)
        if not isinstance(nested, Mapping):
            continue
        result = dict(nested)
        metadata = payload.get("metadata")
        for key in _TRACE_FIELDS:
            value = payload.get(key)
            if value is None and isinstance(metadata, Mapping):
                value = metadata.get(key)
            if value is not None:
                result.setdefault(key, value)
        result.setdefault("role", role.value)
        return result
    return payload


def _diagnostics(error: ValidationError) -> tuple[ContractDiagnostic, ...]:
    diagnostics: list[ContractDiagnostic] = []
    for item in error.errors():
        location = item.get("loc", ())
        path = ".".join(str(part) for part in location) or "$"
        diagnostics.append(
            ContractDiagnostic(
                path=path,
                code=str(item.get("type", "validation_error")),
                message=str(item.get("msg", "invalid value")),
            )
        )
    return tuple(diagnostics)


__all__ = ["AIContractRegistry", "AIContractValidationError", "ContractDiagnostic", "ROLE_MODELS"]
