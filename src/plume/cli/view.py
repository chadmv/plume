"""`plume view`: opens the live viewer window on a recipe, or on a sheet folder (`plume run`'s output folder)
with the Sheet tab only and no simulation (the optional `view` extra)."""

from pathlib import Path

from plume.recipe.load import load_recipe

INSTALL_HINT = "uv sync --extra view"


class ViewUnavailable(Exception):
    """The viewer cannot open: its extra is not installed."""


class ViewUsageError(Exception):
    """The command line asked the viewer for something it does not do."""


def run_view(recipe_path: Path, preview: bool, device: str, sets: tuple[str, ...], cache_gb: float,
             out: str | None = None) -> None:
    """Opens the recipe (a RecipeError leaves before any window opens), or a sheet folder, then runs the
    window until it is closed. Stills and clips go under `out` when given."""
    if recipe_path.is_dir():
        _view_sheet_folder(recipe_path, preview, sets, out)
        return
    load_recipe(recipe_path, preview=preview, sets=sets)  # a recipe error exits 2 whether or not the extra is in
    require_view_extra()
    from plume.view.app import run_viewer
    from plume.view.session import Session

    session = Session.open(recipe_path, preview=preview, sets=sets, device=device, cache_gb=cache_gb)
    run_viewer(session, out)


def _view_sheet_folder(folder: Path, preview: bool, sets: tuple[str, ...], out: str | None) -> None:
    if preview or sets:
        raise ViewUsageError("--preview and --set change a recipe; a sheet folder is shown as it is "
                             "(open the folder's preview/ for the preview sheet)")
    from plume.view.sheet_player import SheetFolderError, SheetSource

    try:
        source = SheetSource.from_folder(folder)
    except SheetFolderError as error:
        raise ViewUsageError(str(error)) from None
    require_view_extra()
    from plume.view.sheet_app import run_sheet_viewer

    run_sheet_viewer(folder, source, out)


def require_view_extra() -> None:
    """Raises ViewUnavailable, naming the install command, when the window's packages are missing."""
    try:
        import glfw  # noqa: F401
        import imgui_bundle  # noqa: F401
        import OpenGL  # noqa: F401
    except ImportError as error:
        raise ViewUnavailable(f"plume view needs the view extra ({error.name} is missing); install it with: "
                              f"{INSTALL_HINT}") from None
