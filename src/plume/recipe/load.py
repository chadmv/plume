"""Loading a recipe: parse the TOML, merge its `extends` parents, apply `--set`, build and check it,
apply --preview, then fill dependent defaults.

The steps run in that order because each needs the previous one's result: `--set` may change a value a
parent gave, and preview changes the frame count that the default column count depends on.
"""

import dataclasses
import math
from pathlib import Path

from plume.recipe.build import build
from plume.recipe.rules import check_output_name, check_rules
from plume.recipe.schema import Recipe
from plume.recipe.variation import RecipeOrigin, apply_sets, read_toml, resolve_extends


def load_recipe(path: Path, preview: bool = False, sets: tuple[str, ...] = ()) -> Recipe:
    """Reads the recipe at `path` and returns it fully resolved."""
    return load_recipe_with_origin(path, preview, sets)[0]


def load_recipe_with_origin(path: Path, preview: bool = False,
                            sets: tuple[str, ...] = ()) -> tuple[Recipe, RecipeOrigin]:
    """The fully resolved recipe at `path`, and the parents and overrides that shaped it."""
    table, chain = resolve_extends(read_toml(path), path)
    recipe = resolve_table(apply_sets(table, tuple(sets)), path.stem, preview)
    return recipe, RecipeOrigin(extends_chain=chain, sets=tuple(sets))


def resolve_table(table: dict, recipe_stem: str, preview: bool = False) -> Recipe:
    """The fully resolved recipe of a merged table (parents and overrides already applied)."""
    recipe = parse_recipe(table)
    if preview:
        recipe = apply_preview(recipe)
    return fill_dependent_defaults(recipe, recipe_stem)


def parse_recipe(table: dict) -> Recipe:
    """Builds and checks a recipe from a parsed TOML table, with schema defaults only."""
    recipe = build(Recipe, table)
    check_rules(recipe)
    return recipe


def apply_preview(recipe: Recipe) -> Recipe:
    """Coarsens the grid so its longest axis has `preview.longest_axis_cells` and uses preview frames.

    Fewer frames would make each step longer, so preview_substeps adds substeps to keep the step length in
    seconds that of the full run, and a preview stays a coarse version of the final look (D30).
    """
    preview = recipe.preview
    cell_m = max(recipe.domain.size_m) / preview.longest_axis_cells
    substeps = preview_substeps(recipe.time.frames, recipe.time.substeps, preview.frames)
    return dataclasses.replace(
        recipe,
        domain=dataclasses.replace(recipe.domain, cell_m=cell_m),
        time=dataclasses.replace(recipe.time, frames=preview.frames, substeps=substeps),
        output=dataclasses.replace(recipe.output, frame_px=preview.frame_px, columns=0),
    )


def preview_substeps(frames: int, substeps: int, preview_frames: int) -> int:
    """Substeps per preview frame that give the full run's step length over the same duration.

    The full run takes `frames * substeps` steps; the preview spreads the same count over its own frames.
    When that does not divide evenly the count rounds up, so a preview step is never longer than a full one.
    """
    return max(1, math.ceil(frames * substeps / preview_frames))


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
