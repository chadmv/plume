"""The viewer's session: the opened recipe, its live run, and what a change on disk does.

A reload whose resolved recipe is unchanged (a comment, a reordered key) does nothing; any other change
starts a new run from time 0, replacing the old one as it lands. A recipe error leaves the last good run
playing and holds the message `plume check` would print, for a red banner, until the file is fixed.
(Per-table stages that redraw without re-running arrive in slice V2.)
"""

import time
from pathlib import Path

from plume.recipe.derived import Derived, derive
from plume.recipe.errors import RecipeError
from plume.recipe.load import load_recipe_with_origin
from plume.recipe.schema import Recipe
from plume.sim.device import init_device
from plume.view.live_run import LiveRun
from plume.view.recipe_watch import RecipeWatch, chain_paths
from plume.view.viewport import Viewport

GIGABYTE = 2**30


class Session:
    """Owns the recipe and the run. Call `update` once per window update."""

    def __init__(self, recipe_path: Path, preview: bool, sets: tuple[str, ...], device: str, cache_gb: float,
                 recipe: Recipe, chain: tuple[str, ...]):
        self.recipe_path = recipe_path
        self.preview = preview
        self.sets = sets
        self.device = device
        self.budget_bytes = cache_gb * GIGABYTE
        self.error: str | None = None
        self.watch = RecipeWatch(chain_paths(recipe_path, chain))
        self.runs_started = 0
        self._start(recipe)

    @classmethod
    def open(cls, recipe_path: Path, preview: bool, sets: tuple[str, ...], device: str,
             cache_gb: float) -> "Session":
        """Loads the recipe (a RecipeError propagates: nothing opens) and starts its run."""
        recipe, origin = load_recipe_with_origin(recipe_path, preview=preview, sets=sets)
        return cls(recipe_path, preview, sets, init_device(device), cache_gb, recipe, origin.extends_chain)

    def update(self, now_s: float | None = None) -> None:
        """Follows the files, then simulates one frame of the run if it is still going."""
        if self.watch.changed(now_s):
            self.reload()
        self.advance()

    def advance(self) -> None:
        """One frame of the run; a recipe error mid-run (a frame needing too many steps) stops it and
        shows the message, keeping the frames that landed."""
        if self.run.done or self.run.stopped:
            self.run.poll_assembly()
            return
        try:
            self.run.advance()
        except RecipeError as error:
            self.run.cancel()
            self.run.stopped = True
            self.error = f"recipe error: {error}"

    def reload(self) -> bool:
        """Reads the recipe again; True when a new run started."""
        try:
            recipe, origin = load_recipe_with_origin(self.recipe_path, preview=self.preview, sets=self.sets)
        except RecipeError as error:
            self.error = f"recipe error: {error}"
            return False
        self.error = None
        self.watch.follow(chain_paths(self.recipe_path, origin.extends_chain))
        if recipe == self.recipe and not self.run.stopped:
            return False
        self.run.cancel()
        self._start(recipe)
        return True

    def set_preview(self, preview: bool) -> None:
        """The Full or Preview toggle: re-runs on the other grid."""
        if preview != self.preview:
            self.preview = preview
            self.reload()

    @property
    def run_seconds(self) -> float:
        """The run's wall time: final once done, else so far."""
        return self.run.elapsed_s if self.run.done else time.perf_counter() - self.run.started_s

    def _start(self, recipe: Recipe) -> None:
        self.recipe = recipe
        self.derived: Derived = derive(recipe)
        self.run = LiveRun(recipe, self.derived, self.device, self.budget_bytes)
        self.viewport = Viewport(recipe, self.derived, self.device)
        self.runs_started += 1
