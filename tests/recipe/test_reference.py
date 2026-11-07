from pathlib import Path

from plume.recipe.reference import reference_markdown

REPO = Path(__file__).resolve().parents[2]


def test_recipe_reference_is_current():
    current = (REPO / "docs" / "recipe-reference.md").read_text()
    assert current == reference_markdown(), "run: uv run python -m plume.recipe.reference"
