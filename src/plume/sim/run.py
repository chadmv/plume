"""The frame loop: warmup, then each frame's steps followed by a capture of that frame.

The simulation clock starts at 0 when warmup begins and is always `step count * dt`, so times never drift.
Frame `i` is captured after `warmup_s + (i + 1) / fps` of simulated time: the last frame lands exactly at
the end of the duration, and the first frame already shows the effect starting.
"""

from collections.abc import Callable

from plume.recipe.derived import Derived
from plume.recipe.schema import Recipe
from plume.sim.grid import Grid, make_grid
from plume.sim.stepper import Stepper

Capture = Callable[[int, Grid], None]


def simulate(recipe: Recipe, derived: Derived, device: str, capture: Capture) -> None:
    """Runs the whole recipe, calling `capture(frame_index, grid)` once per frame, in order."""
    grid = make_grid(derived, recipe.domain.cell_m, recipe.domain.faces, recipe.domain.ambient_k, device)
    stepper = Stepper(grid, recipe, derived.dt_s)
    step_count = 0
    for _ in range(derived.warmup_steps):
        stepper.step(step_count * derived.dt_s)
        step_count += 1
    for frame in range(recipe.time.frames):
        for _ in range(derived.steps_per_frame):
            stepper.step(step_count * derived.dt_s)
            step_count += 1
        capture(frame, grid)
