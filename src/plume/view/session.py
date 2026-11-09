"""The viewer's session: the opened recipe, the viewer's edits, the A and B runs, and what a change does.

A change (a reload from disk, or an edit in the panel) resolves the recipe again, the file merged with its
parents with the unsaved edits on top, and the stages of the keys that changed (V11) pick the work:
- simulation: a new run from time 0;
- render or sheet: a re-capture of the kept frames with the new settings (a re-run instead when the run is
  still simulating or its cache skipped frames);
- look: a new viewport over the same run (a redraw);
- nothing on screen (a comment, `[preview]` with Preview off): the new recipe is taken, nothing else.
A change that does work makes the current A into B (Compare, V12), except while A is still simulating: then
A is replaced and B kept. A recipe error leaves the last good run playing and holds the message `plume
check` would print, for a red banner, until the file is fixed; a rejected edit is not applied and its
message goes back to the panel.
"""

import dataclasses
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plume.recipe.derived import Derived, derive
from plume.recipe.errors import RecipeError
from plume.recipe.load import parse_recipe, resolve_table
from plume.recipe.schema import LOOK_STAGE, RENDER_STAGE, SHEET_STAGE, SIMULATION_STAGE, Recipe
from plume.recipe.variation import EMITTER_BY_INDEX, apply_values, read_toml, resolve_extends, set_item
from plume.sim.device import init_device
from plume.view.live_run import LiveRun
from plume.view.recipe_keys import changed_paths, changed_stages, table_paths, values_by_path
from plume.view.recipe_watch import RecipeWatch, chain_paths, reachable_chain
from plume.view.recipe_writer import write_edits
from plume.view.viewport import Viewport

GIGABYTE = 2**30
SIGNIFICANT_DIGITS = 6  # an edited float is rounded to this many (ImGui's drag fields are float32)

RERUN, RECAPTURE, REDRAW, TAKE = "rerun", "recapture", "redraw", "take"


@dataclass
class Snapshot:
    """One side of Compare: a resolved recipe, the run whose frames it shows, and the viewport drawing it."""

    recipe: Recipe
    run: LiveRun
    viewport: Viewport


class Session:
    """Owns the recipe, the edits and the runs. Call `update` once per window update."""

    def __init__(self, recipe_path: Path, preview: bool, sets: tuple[str, ...], device: str, cache_gb: float,
                 merged: dict, chain: tuple[str, ...]):
        self.recipe_path = recipe_path
        self.preview = preview
        self.device = device
        self.budget_bytes = cache_gb * GIGABYTE
        self.error: str | None = None
        self.notice: str | None = None  # the last Save's outcome, for the panel
        self.kept_edits_note: str | None = None  # unsaved edits applied over a reloaded file, for a banner
        self.watch = RecipeWatch(chain_paths(recipe_path, chain))
        self.runs_started = 0
        self.compare: Snapshot | None = None  # B
        self._file_broken = False  # the last reload could not read the file or its parents
        self._take_file(merged)
        self.edits: dict[str, Any] = _edits_from_sets(sets, merged)  # --set values start as edits (V14)
        recipe, self.base_recipe = self._resolve(self.edits)
        self.current = self._new_run(recipe)

    @classmethod
    def open(cls, recipe_path: Path, preview: bool, sets: tuple[str, ...], device: str,
             cache_gb: float) -> "Session":
        """Loads the recipe with `--set` as edits (a RecipeError propagates: nothing opens) and starts its
        run."""
        merged, chain = resolve_extends(read_toml(recipe_path), recipe_path)
        return cls(recipe_path, preview, sets, init_device(device), cache_gb, merged, chain)

    # -- A, as V1 knew it ----------------------------------------------------------------------------------

    @property
    def recipe(self) -> Recipe:
        return self.current.recipe

    @property
    def run(self) -> LiveRun:
        return self.current.run

    @property
    def viewport(self) -> Viewport:
        return self.current.viewport

    @property
    def derived(self) -> Derived:
        return self.current.run.derived

    # -- the window's calls ----------------------------------------------------------------------------------

    def update(self, now_s: float | None = None) -> None:
        """Follows the files, then captures one frame of the run if it is still going."""
        if self.watch.changed(now_s):
            self.reload(from_disk=True)
        self.advance()

    def advance(self) -> None:
        """One frame of A's run; a recipe error mid-run (a frame needing too many steps) stops it and shows
        the message, keeping the frames that landed."""
        if self.compare is not None:
            self.compare.run.poll_assembly()
        run = self.run
        if not run.capturing:
            run.poll_assembly()
            return
        try:
            run.advance()
        except RecipeError as error:
            run.cancel()
            self.error = f"recipe error: {error}"

    def reload(self, from_disk: bool = False) -> bool:
        """Reads the recipe again, with the unsaved edits on top; True when a new run started. `from_disk`
        (the watch saw a change) notes edits kept over the file for a banner. The file is taken even when
        the edits no longer fit it (an emitter they name was renamed), so Reset and Revert work against the
        file as it is now."""
        try:
            merged, chain = resolve_extends(read_toml(self.recipe_path), self.recipe_path)
        except RecipeError as error:
            self.error = f"recipe error: {error}"
            self._file_broken = True
            self.watch.follow(reachable_chain(self.recipe_path))
            return False
        self._file_broken = False
        self.watch.follow(chain_paths(self.recipe_path, chain))
        self._take_file(merged)
        if from_disk:
            self.kept_edits_note = (f"{len(self.edits)} unsaved viewer edit{'s' if len(self.edits) != 1 else ''} "
                                    "kept over the reloaded recipe") if self.edits else None
        try:
            recipe, base = self._resolve(self.edits)
        except RecipeError as error:
            edits = f" (with {len(self.edits)} unsaved viewer edits; Revert drops them)" if self.edits else ""
            self.error = f"recipe error: {error}{edits}"
            return False
        self.error = None
        return self._apply(recipe, base) == RERUN

    def set_preview(self, preview: bool) -> None:
        """The Full or Preview toggle: re-runs on the other grid. If the recipe has an error, the toggle
        stays where it was (the banner says why)."""
        if preview != self.preview:
            self.preview = preview
            if not self.reload() and self.error is not None:
                self.preview = not preview

    def edit(self, path: str, value: Any) -> str | None:
        """Applies one edit from the panel, checked by `plume check`'s rules first; returns the check's
        message when it is rejected (nothing changes), else None. A value equal to the file's drops the
        edit."""
        value = _toml_value(value)
        edits = dict(self.edits)
        if self._file_values.get(path, _ABSENT) == _comparable(value):
            edits.pop(path, None)
        else:
            edits[path] = value
        return self._set_edits(edits)

    def reset(self, path: str) -> str | None:
        """Drops one edit (the panel's Reset)."""
        return self._set_edits({key: value for key, value in self.edits.items() if key != path})

    def revert(self) -> str | None:
        """Drops every edit (Revert)."""
        return self._set_edits({})

    def save(self) -> str:
        """Writes the edits into the opened recipe (V14) and reloads it; returns the line for the panel."""
        if not self.edits:
            return "nothing to save"
        count = len(self.edits)
        try:
            notes = write_edits(self.recipe_path, self.edits, self._merged)
        except RecipeError as error:
            self.notice = f"not saved: {error}"
            return self.notice
        self.edits = {}
        self.reload()
        self.notice = "; ".join([f"saved {count} key{'s' if count != 1 else ''} to {self.recipe_path.name}",
                                 *notes])
        return self.notice

    # -- what the panel and Compare read -------------------------------------------------------------------

    def is_set_by_recipe(self, path: str) -> bool:
        """Whether the file or its parents set the key (else it is the schema's default)."""
        return path in self._file_paths

    def compare_differences(self) -> list[str]:
        """The keys whose resolved values differ between A and B."""
        if self.compare is None:
            return []
        return changed_paths(self.compare.recipe, self.recipe)

    @property
    def run_seconds(self) -> float:
        """The run's wall time: final once done or stopped, else so far."""
        if self.run.done or self.run.stopped:
            return self.run.elapsed_s
        return time.perf_counter() - self.run.started_s

    # -- inside -----------------------------------------------------------------------------------------------

    def _take_file(self, merged: dict) -> None:
        self._merged = merged
        self._file_paths = table_paths(merged)
        try:
            self._file_values = {path: _comparable(value)
                                 for path, value in values_by_path(parse_recipe(merged)).items()}
        except RecipeError:
            self._file_values = {}  # the file alone is broken (an edit fixes it); no edit is dropped as equal

    def _resolve(self, edits: dict[str, Any], merged: dict | None = None) -> tuple[Recipe, Recipe]:
        """The run's recipe and the panel's (before --preview and dependent defaults) for these edits."""
        table = apply_values(self._merged if merged is None else merged, edits)
        base = parse_recipe(table)
        return resolve_table(table, self.recipe_path.stem, self.preview), base

    def _set_edits(self, edits: dict[str, Any]) -> str | None:
        try:
            recipe, base = self._resolve(edits)
        except RecipeError as error:
            return str(error)
        self.edits = edits
        if not self._file_broken:
            self.error = None  # the edits fit the file now (the reload's error was the edits')
        if self.kept_edits_note and not edits:
            self.kept_edits_note = None
        self._apply(recipe, base)
        return None

    def _apply(self, recipe: Recipe, base: Recipe) -> str:
        """Moves to a newly resolved recipe; returns the work it did (RERUN, RECAPTURE, REDRAW or TAKE)."""
        self.base_recipe = base
        current = self.current
        stages = changed_stages(current.recipe, recipe)
        if SIMULATION_STAGE in stages or (not stages and current.run.stopped):
            work = RERUN
        elif stages & {RENDER_STAGE, SHEET_STAGE}:
            work = RECAPTURE if current.run.can_recapture() else RERUN
        elif LOOK_STAGE in stages:
            work = REDRAW
        else:
            self.current = dataclasses.replace(current, recipe=recipe)
            return TAKE
        if not current.run.capturing:
            self.compare = current  # A becomes B; while A is still simulating or re-capturing, B stays
        if work == RERUN:
            self.current = self._new_run(recipe)
        elif work == RECAPTURE:
            run = LiveRun.recapture(current.run, recipe)
            self.current = Snapshot(recipe, run, Viewport(recipe, run.derived, self.device))
        else:
            self.current = Snapshot(recipe, current.run, Viewport(recipe, current.run.derived, self.device))
        if current.run not in (self.current.run, getattr(self.compare, "run", None)):
            current.run.cancel()  # a run nobody shows any more
        return work

    def _new_run(self, recipe: Recipe) -> Snapshot:
        derived = derive(recipe)
        held = self.compare.run.cache.stored_bytes if self.compare is not None else 0
        run = LiveRun(recipe, derived, self.device, max(self.budget_bytes - held, 0.0),
                      shared_with_compare=held > 0)
        self.runs_started += 1
        return Snapshot(recipe, run, Viewport(recipe, derived, self.device))


_ABSENT = object()


def _edits_from_sets(sets: tuple[str, ...], merged: dict) -> dict[str, Any]:
    """`--set` items as edits, an emitter named by index renamed to its name (Save finds emitters by name)."""
    edits: dict[str, Any] = {}
    emitters = merged.get("emitter")
    for item in sets:
        key, value = set_item(item)
        first, _, rest = key.partition(".")
        match = EMITTER_BY_INDEX.match(first)
        if match and rest and isinstance(emitters, list) and int(match.group(1)) < len(emitters):
            emitter = emitters[int(match.group(1))]
            if isinstance(emitter, dict) and isinstance(emitter.get("name"), str):
                key = f"emitter.{emitter['name']}.{rest}"
        for leaf, leaf_value in _leaves(key, value):
            edits.pop(leaf, None)  # a later --set of the same key wins, and goes last
            edits[leaf] = leaf_value
    return edits


def _leaves(key: str, value: Any) -> list[tuple[str, Any]]:
    """A table-valued --set (`forces.turbulence={ scale_m = 0.1 }`) as one edit per key, so the panel marks
    each and Save keeps the file's own table layout."""
    if not isinstance(value, dict):
        return [(key, value)]
    return [leaf for name, item in value.items() for leaf in _leaves(f"{key}.{name}", item)]


def _toml_value(value: Any) -> Any:
    """A panel value as a TOML value: floats rounded, vectors as lists."""
    if isinstance(value, float):
        return float(f"{value:.{SIGNIFICANT_DIGITS}g}") if math.isfinite(value) else value
    if isinstance(value, (tuple, list)):
        return [_toml_value(item) for item in value]
    return value


def _comparable(value: Any) -> Any:
    """A value in the form both recipes and edits compare in (tuples and lists alike)."""
    if isinstance(value, (tuple, list)):
        return tuple(_comparable(item) for item in value)
    return value
