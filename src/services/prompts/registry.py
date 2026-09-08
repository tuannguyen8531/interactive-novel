"""Load, render and snapshot versioned prompt assets."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.application.contracts.ai import AIPromptRole, RoleInput

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_INCLUDE = re.compile(r"\{\{>\s*([^{}]+?)\s*\}\}")
_PROMPT_CACHE: ContextVar[dict[tuple[str, str], PromptDefinition] | None] = ContextVar(
    "interactive_novel_prompt_cache",
    default=None,
)


class PromptRegistryError(ValueError):
    """Prompt metadata or rendering is invalid."""


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    role: AIPromptRole
    semantic_version: str
    input_contract: str
    output_schema_version: str
    template_name: str
    content: str
    required_variables: tuple[str, ...]
    changelog: str
    template_hash: str

    def render(self, variables: Mapping[str, str]) -> str:
        missing = [name for name in self.required_variables if name not in variables]
        if missing:
            raise PromptRegistryError(f"Prompt {self.role.value} is missing variables: {', '.join(missing)}")
        rendered = _render(self.content, variables)
        if _PLACEHOLDER.search(rendered):
            raise PromptRegistryError(f"Prompt {self.role.value} contains unresolved variables.")
        return rendered.strip()

    def snapshot(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "semantic_version": self.semantic_version,
            "input_contract": self.input_contract,
            "output_schema_version": self.output_schema_version,
            "template": self.template_name,
            "template_hash": self.template_hash,
            "required_variables": list(self.required_variables),
            "changelog": self.changelog,
        }


@dataclass(frozen=True, slots=True)
class RepairPromptDefinition:
    semantic_version: str
    template_hash: str
    content: str
    system_content: str

    def render(
        self,
        *,
        original_prompt: str,
        role: str,
        schema_name: str,
        invalid_output: str,
        diagnostics: str,
        story_language: str,
    ) -> str:
        repair_input = json.dumps(
            {
                "role": role,
                "schema_name": schema_name,
                "story_language": story_language,
                "diagnostics": diagnostics,
                "invalid_output": invalid_output,
            },
            ensure_ascii=False,
        )
        return _render(self.content, {"original_prompt": original_prompt, "repair_input_json": repair_input}).strip()

    def snapshot(self) -> dict[str, str]:
        return {"semantic_version": self.semantic_version, "template_hash": self.template_hash}


class PromptRegistry:
    """Immutable prompt definitions loaded from the bundled manifest."""

    default_root = Path(__file__).resolve().parents[2] / "prompts"

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or self.default_root).resolve()
        self._definitions: dict[AIPromptRole, PromptDefinition] = {}
        self._repair: RepairPromptDefinition | None = None
        self._manifest = self._load_manifest()

    def roles(self) -> tuple[AIPromptRole, ...]:
        return tuple(AIPromptRole)

    def get(self, role: AIPromptRole | str) -> PromptDefinition:
        normalized = AIPromptRole(role)
        scoped_cache = _PROMPT_CACHE.get()
        cache_key = (str(self.root), normalized.value)
        if scoped_cache is not None and cache_key in scoped_cache:
            return scoped_cache[cache_key]
        if normalized in self._definitions:
            return self._definitions[normalized]
        try:
            metadata = self._manifest[normalized.value]
        except KeyError as error:
            raise PromptRegistryError(f"No prompt registered for role {normalized.value}.") from error
        template_name = _required_text(metadata, "template", normalized.value)
        version = _required_text(metadata, "semantic_version", normalized.value)
        content = self._read_template(template_name)
        content = _render(content, {"prompt_version": version})
        placeholders = tuple(dict.fromkeys(_PLACEHOLDER.findall(content)))
        required_variables = tuple(_required_variables(metadata, normalized.value))
        if set(placeholders) != set(required_variables):
            raise PromptRegistryError(
                f"Prompt {normalized.value} variable manifest mismatch: "
                f"template={placeholders!r}, manifest={required_variables!r}"
            )
        definition = PromptDefinition(
            role=normalized,
            semantic_version=version,
            input_contract=_required_text(metadata, "input_contract", normalized.value),
            output_schema_version=_required_text(metadata, "output_schema_version", normalized.value),
            template_name=template_name,
            content=content,
            required_variables=required_variables,
            changelog=_required_text(metadata, "changelog", normalized.value),
            template_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
        self._definitions[normalized] = definition
        if scoped_cache is not None:
            scoped_cache[cache_key] = definition
        return definition

    def render(self, role: AIPromptRole | str, *, input_json: str) -> str:
        return self.get(role).render({"input_json": input_json})

    def render_input(self, role: AIPromptRole | str, role_input: RoleInput) -> str:
        normalized = AIPromptRole(role)
        if role_input.role != normalized:
            raise PromptRegistryError(f"Role input is for {role_input.role.value}, but prompt requested {normalized.value}.")
        return self.render(normalized, input_json=role_input.model_dump_json())

    def render_repair(
        self,
        role: AIPromptRole | str,
        *,
        invalid_output: str,
        diagnostics: str,
        original_prompt: str = "",
        schema_name: str | None = None,
        story_language: str = "en",
    ) -> str:
        return self.get_repair().render(
            original_prompt=original_prompt,
            role=str(role),
            schema_name=schema_name or self.get(role).output_schema_version,
            invalid_output=invalid_output,
            diagnostics=diagnostics,
            story_language=story_language,
        )

    def get_repair(self) -> RepairPromptDefinition:
        if self._repair is not None:
            return self._repair
        metadata = self._manifest["repair"]
        template = self._read_template(_required_text(metadata, "template", "repair"))
        system_section, separator, content = template.partition("\n\n# User\n\n")
        if not system_section.startswith("# System\n\n") or not separator or not content.strip():
            raise PromptRegistryError("Repair template requires System and User sections.")
        system_content = system_section.removeprefix("# System\n\n").strip()
        if not system_content:
            raise PromptRegistryError("Repair System section cannot be empty.")
        required = set(_required_variables(metadata, "repair"))
        if set(_PLACEHOLDER.findall(content)) != required or _PLACEHOLDER.search(system_content):
            raise PromptRegistryError("Repair template variables do not match its manifest.")
        if required != {"original_prompt", "repair_input_json"}:
            raise PromptRegistryError("Unsupported repair template variables.")
        self._repair = RepairPromptDefinition(
            semantic_version=_required_text(metadata, "semantic_version", "repair"),
            template_hash=hashlib.sha256(json.dumps([system_content, content]).encode("utf-8")).hexdigest(),
            content=content,
            system_content=system_content,
        )
        return self._repair

    def _read_template(self, name: str, *, allow_includes: bool = True) -> str:
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise PromptRegistryError(f"Prompt template not found inside registry root: {name}")
        content = path.read_text(encoding="utf-8")
        if not allow_includes and _INCLUDE.search(content):
            raise PromptRegistryError("Nested prompt includes are not supported.")
        return _INCLUDE.sub(lambda match: self._read_template(match[1].strip(), allow_includes=False).rstrip(), content)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {**{role.value: self.get(role).snapshot() for role in self.roles()}, "repair": self.get_repair().snapshot()}

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        path = self.root / "manifest.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PromptRegistryError(f"Unable to load prompt manifest: {path}") from error
        if not isinstance(payload, dict):
            raise PromptRegistryError("Prompt manifest must be a JSON object.")
        expected = {*(role.value for role in AIPromptRole), "repair"}
        if set(payload) != expected:
            raise PromptRegistryError("Prompt manifest must contain the AI roles and repair template.")
        return {str(role): dict(metadata) for role, metadata in payload.items()}


@contextmanager
def prompt_cache_scope() -> Iterator[None]:
    """Share immutable prompt definitions within one graph/job context."""

    token = _PROMPT_CACHE.set({})
    try:
        yield
    finally:
        _PROMPT_CACHE.reset(token)


def _render(content: str, variables: Mapping[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda match: variables.get(match.group(1), match.group(0)), content)


def _required_text(metadata: Mapping[str, Any], key: str, role: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PromptRegistryError(f"Prompt {role} manifest field {key} must be a non-empty string.")
    return value


def _required_variables(metadata: Mapping[str, Any], role: str) -> list[str]:
    value = metadata.get("required_variables")
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise PromptRegistryError(f"Prompt {role} required_variables must be a list of non-empty strings.")
    return value


__all__ = ["PromptDefinition", "PromptRegistry", "PromptRegistryError", "prompt_cache_scope"]
