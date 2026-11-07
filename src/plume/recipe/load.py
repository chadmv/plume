"""Loading a recipe: parse the TOML, build and check it, apply --preview, then fill dependent defaults.

The four steps run in that order because each needs the previous one's result: preview changes the frame
count that the default column count depends on.
"""

import dataclasses
import math
import tomllib
from pathlib import Path

from plume.recipe.build import build
from plume.recipe.errors import RecipeError
from plume.recipe.rules import check_output_name, check_rules
from plume.recipe.schema import Recipe


def load_recipe(path: Path, preview: bool = False) -> Recipe:
    """Reads the recipe at `path` and returns it fully resolved."""
    recipe = parse_recipe(_read_toml(path))
    if preview:
        recipe = apply_preview(recipe)
    return fill_dependent_defaults(recipe, path.stem)


def parse_recipe(table: dict) -> Recipe:
    """Builds and checks a recipe from a parsed TOML table, with schema defaults only."""
    recipe = build(Recipe, table)
    check_rules(recipe)
    return recipe


def apply_preview(recipe: Recipe) -> Recipe:
    """Coarsens the grid so its longest axis has `preview.longest_axis_cells` and uses preview frames."""
    preview = recipe.preview
    cell_m = max(recipe.domain.size_m) / preview.longest_axis_cells
    return dataclasses.replace(
        recipe,
        domain=dataclasses.replace(recipe.domain, cell_m=cell_m),
        time=dataclasses.replace(recipe.time, frames=preview.frames),
        output=dataclasses.replace(recipe.output, frame_px=preview.frame_px, columns=0),
    )


def fill_dependent_defaults(recipe: Recipe, recipe_stem: str) -> Recipe:
    """Replaces the 'empty means derived' defaults with their values, so the settings log is explicit."""
    output = recipe.output
    check_output_name(output.name or recipe_stem)
    columns = output.columns or math.ceil(math.sqrt(recipe.time.frames))
    ambient = recipe.domain.ambient_k
    emitters = tuple(
        dataclasses.replace(e, temperature_k=ambient) if e.temperature_k == -1.0 else e
        for e in recipe.emitter
    )
    return dataclasses.replace(
        recipe,
        emitter=emitters,
        camera=dataclasses.replace(recipe.camera, seat=recipe.camera.seat or emitters[0].name),
        output=dataclasses.replace(output, name=output.name or recipe_stem, columns=columns),
    )


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        raise RecipeError(f"recipe not found: {path}") from None
    except tomllib.TOMLDecodeError as error:
        raise RecipeError(f"{path} is not valid TOML: {error}") from None
