"""Validate and load recipe YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecipeError(ValueError):
    """Recipe failed schema or content validation."""


class RecipeInput(BaseModel):
    """One declared input of a recipe."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "vector", "raster", "string", "int", "float", "daterange", "date", "bbox"
    ]
    default: Any | None = None
    hint: str | None = None
    min: float | int | None = None
    max: float | int | None = None


class RecipeStep(BaseModel):
    """One action invocation in a recipe."""

    model_config = ConfigDict(extra="forbid")

    action: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def _action_format(cls, v: str) -> str:
        if not v or "." not in v:
            raise ValueError(f"action must be dotted (e.g. 'catalog.search'); got {v!r}")
        return v


class Recipe(BaseModel):
    """A one-click Terranova workflow defined in YAML."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    inputs: dict[str, RecipeInput] = Field(default_factory=dict)
    steps: list[RecipeStep]

    @field_validator("steps")
    @classmethod
    def _at_least_one_step(cls, v: list[RecipeStep]) -> list[RecipeStep]:
        if not v:
            raise ValueError("recipe must have at least one step")
        return v


# --------------------------------------------------------------------------- #
def load_recipe(path: Path) -> Recipe:
    """Load and validate a single ``.yaml`` recipe."""
    import yaml

    text = Path(path).read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RecipeError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise RecipeError(f"{path}: top-level must be a mapping")
    try:
        return Recipe.model_validate(raw)
    except ValueError as exc:
        raise RecipeError(f"{path}: {exc}") from exc


def load_recipe_dir(directory: Path) -> list[Recipe]:
    """Load every ``*.yaml`` file in ``directory``."""
    out: list[Recipe] = []
    for path in sorted(Path(directory).glob("*.yaml")):
        out.append(load_recipe(path))
    return out
