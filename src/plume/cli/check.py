"""`plume check`: validates a recipe and prints its resolved settings without simulating."""

from pathlib import Path

from plume.recipe.derived import derive
from plume.recipe.load import load_recipe_with_origin
from plume.recipe.serialize import recipe_to_toml


def run_check(recipe_path: Path, preview: bool, sets: tuple[str, ...] = ()) -> None:
    """Prints the grid size and the resolved recipe; raises RecipeError for an invalid recipe."""
    recipe, origin = load_recipe_with_origin(recipe_path, preview=preview, sets=sets)
    derived = derive(recipe)
    nx, ny, nz = derived.cells
    print(f"ok: {recipe_path}")
    print(f"grid {nx} x {ny} x {nz} cells of {recipe.domain.cell_m:.6f} m, "
          f"{recipe.time.frames} frames at {derived.fps:.6f} fps")
    print()
    print(recipe_to_toml(recipe, derived, device="(chosen at run time)", origin=origin), end="")
