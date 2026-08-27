from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.templates import StoryTemplateRegistry

TEMPLATE_ROOT = Path(__file__).parents[2] / "src" / "templates"


def test_story_template_registry_loads_the_bundled_catalog() -> None:
    registry = StoryTemplateRegistry()

    assert registry.ids() == ("school_romance", "mystery", "fantasy_adventure")
    assert registry.get("MYSTERY").name == "Mystery"
    assert registry.get("fantasy_adventure").defaults.violence_ceiling.value == "restrained"
    assert registry.get("mystery").narrative_profile.primary_focus == "romance"


def test_story_template_public_shape_is_json_serializable() -> None:
    template = StoryTemplateRegistry().get("school_romance")

    public = template.as_public_dict()

    json.dumps(public)
    assert public["id"] == "school_romance"
    assert public["opening_guidance"]
    assert public["defaults"]["rating"] == "teen_14_plus"
    assert public["narrative_profile"]["romance_priority"] == "high"


def test_story_template_registry_discovers_unlisted_json_files(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "story-template-manifest", "templates": ["school_romance"]}),
        encoding="utf-8",
    )
    shutil.copyfile(
        TEMPLATE_ROOT / "templates" / "school_romance.json",
        template_dir / "school_romance.json",
    )
    extra = json.loads((template_dir / "school_romance.json").read_text(encoding="utf-8"))
    extra["id"] = "slice_of_life"
    extra["name"] = "Slice of life"
    (template_dir / "slice_of_life.json").write_text(json.dumps(extra), encoding="utf-8")

    registry = StoryTemplateRegistry(tmp_path)

    assert registry.ids() == ("school_romance", "slice_of_life")
    assert registry.get("slice_of_life").name == "Slice of life"
