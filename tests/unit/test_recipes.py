"""Recipe loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from terranova.core.recipes import Recipe, RecipeError, load_recipe, load_recipe_dir  # noqa: E402

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
RECIPES_DIR = REPO_ROOT / "recipes"


def test_bundled_recipes_load() -> None:
    """Every bundled recipe must validate against the schema."""
    recipes = load_recipe_dir(RECIPES_DIR)
    assert len(recipes) >= 2
    assert all(isinstance(r, Recipe) for r in recipes)


def test_crop_classification_recipe_shape() -> None:
    crop = load_recipe(RECIPES_DIR / "crop_classification.yaml")
    assert crop.name
    assert "aoi" in crop.inputs
    assert crop.inputs["aoi"].kind == "vector"
    assert crop.steps[0].action == "catalog.search"


def test_invalid_action_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "bad.yaml"
    p.write_text(
        """
name: bad
steps:
  - action: nodot
    params: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(RecipeError):
        load_recipe(p)


def test_empty_steps_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "empty.yaml"
    p.write_text(
        """
name: empty
steps: []
""",
        encoding="utf-8",
    )
    with pytest.raises(RecipeError):
        load_recipe(p)


def test_extra_top_level_field_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "extra.yaml"
    p.write_text(
        """
name: extra
mystery: value
steps:
  - action: catalog.search
""",
        encoding="utf-8",
    )
    with pytest.raises(RecipeError):
        load_recipe(p)


def test_malformed_yaml_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "bad.yaml"
    p.write_text("name: [unclosed", encoding="utf-8")
    with pytest.raises(RecipeError):
        load_recipe(p)
