"""`plume view`: opens the live viewer window on a recipe (the optional `view` extra)."""

from pathlib import Path

INSTALL_HINT = "uv sync --extra view"


class ViewUnavailable(Exception):
    """The viewer cannot open: its extra is not installed, or it was asked to open something it cannot."""


class ViewUsageError(Exception):
    """The command line asked the viewer for something it does not do."""


def run_view(recipe_path: Path, preview: bool, device: str, sets: tuple[str, ...], cache_gb: float) -> None:
    """Opens the recipe (a RecipeError leaves before any window opens), then runs the window until it is
    closed."""
    if recipe_path.is_dir():
        raise ViewUsageError(f"{recipe_path} is a folder; opening a run's output folder (the Sheet tab) comes in "
                             "a later viewer slice. Open a recipe .toml")
    require_view_extra()
    from plume.view.app import run_viewer
    from plume.view.session import Session

    session = Session.open(recipe_path, preview=preview, sets=sets, device=device, cache_gb=cache_gb)
    run_viewer(session)


def require_view_extra() -> None:
    """Raises ViewUnavailable, naming the install command, when the window's packages are missing."""
    try:
        import glfw  # noqa: F401
        import imgui_bundle  # noqa: F401
        import OpenGL  # noqa: F401
    except ImportError as error:
        raise ViewUnavailable(f"plume view needs the view extra ({error.name} is missing); install it with: "
                              f"{INSTALL_HINT}") from None
