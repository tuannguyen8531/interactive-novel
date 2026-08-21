"""Load story templates independently from AI prompt templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import StoryTemplate


class StoryTemplateRegistryError(ValueError):
    """Raised when the story template catalog is invalid or incomplete."""


class StoryTemplateRegistry:
    """Immutable catalog discovered from JSON files under the template directory.

    The manifest's optional ``templates`` list controls display order for known
    IDs. JSON files not listed there are discovered automatically, so adding a
    template does not require a Python change or a manifest edit.
    """

    default_root = Path(__file__).resolve().parent

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or self.default_root).resolve()
        self._manifest = self._load_json(self.root / "manifest.json")
        self._templates: dict[str, StoryTemplate] = {}
        self._load_templates()

    def ids(self) -> tuple[str, ...]:
        return tuple(self._templates)

    def list(self) -> tuple[StoryTemplate, ...]:
        return tuple(self._templates.values())

    def get(self, template_id: str) -> StoryTemplate:
        normalized = template_id.strip().lower()
        try:
            return self._templates[normalized]
        except KeyError as error:
            raise StoryTemplateRegistryError(f"Unknown story template: {template_id}.") from error

    def _load_templates(self) -> None:
        template_dir = self.root / "templates"
        if not template_dir.is_dir():
            raise StoryTemplateRegistryError(f"Story template directory not found: {template_dir}.")
        files = {path.stem: path for path in sorted(template_dir.glob("*.json"))}
        if not files:
            raise StoryTemplateRegistryError(f"No story template JSON files found in {template_dir}.")

        configured_order = self._manifest.get("templates", [])
        if not isinstance(configured_order, list):
            raise StoryTemplateRegistryError("Story template manifest field 'templates' must be a list when provided.")
        ordered_ids = _ordered_ids(configured_order, files)
        for template_id in ordered_ids:
            path = files.get(template_id)
            if path is None:
                raise StoryTemplateRegistryError(f"Story template file not found: {template_dir / f'{template_id}.json'}.")
            template = self._load_template(path, expected_id=template_id)
            if template.id in self._templates:
                raise StoryTemplateRegistryError(f"Story template ID mismatch or duplicate: {template.id}.")
            self._templates[template.id] = template

    @classmethod
    def _load_template(cls, path: Path, *, expected_id: str) -> StoryTemplate:
        data = cls._load_json(path)
        template = StoryTemplate(
            id=_required_text(data, "id"),
            name=_required_text(data, "name"),
            description=_required_text(data, "description"),
            genre=_required_text(data, "genre"),
            default_tone=_required_text(data, "default_tone"),
            prompt_instructions=_required_text(data, "prompt_instructions"),
            default_presets=_mapping(data, "default_presets"),
            opening_guidance=_text_tuple(data, "opening_guidance"),
            version=_required_text(data, "version"),
        )
        if template.id != expected_id:
            raise StoryTemplateRegistryError(
                f"Story template ID mismatch: file {path.name} declares {template.id!r}, expected {expected_id!r}."
            )
        return template

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise StoryTemplateRegistryError(f"Story template file not found: {path}.")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StoryTemplateRegistryError(f"Invalid story template JSON: {path}.") from error
        if not isinstance(value, dict):
            raise StoryTemplateRegistryError(f"Story template must be a JSON object: {path}.")
        return value


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StoryTemplateRegistryError(f"Story template field {key!r} must be non-empty text.")
    return value.strip()


def _ordered_ids(configured_order: list[Any], files: dict[str, Path]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for entry in configured_order:
        if not isinstance(entry, str) or not entry.strip():
            raise StoryTemplateRegistryError("Story template manifest contains an invalid template ID.")
        template_id = entry.strip().lower()
        if template_id in seen:
            raise StoryTemplateRegistryError(f"Story template manifest contains a duplicate template ID: {entry}.")
        if template_id not in files:
            raise StoryTemplateRegistryError(f"Story template file not found for manifest entry: {entry}.")
        seen.add(template_id)
        ordered.append(template_id)
    ordered.extend(template_id for template_id in sorted(files) if template_id not in seen)
    return tuple(ordered)


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise StoryTemplateRegistryError(f"Story template field {key!r} must be an object.")
    return dict(value)


def _text_tuple(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise StoryTemplateRegistryError(f"Story template field {key!r} must be a list of text.")
    return tuple(item.strip() for item in value)


__all__ = ["StoryTemplateRegistry", "StoryTemplateRegistryError"]
