"""The frame loop: warmup, then each frame's steps followed by a capture of that frame.

Time runs in blocks: one per frame, and warmup in blocks of the same base step count (the last one
shorter). A block's start is always `base step count so far * dt`, so the clock never drifts, and the CFL
cap (`sim/step_cap.py`) may split a block into more, shorter steps. Frame `i` is captured after
`warmup_s + (i + 1) / fps` of simulated time: the last frame lands exactly at the end of the duration, and
the first frame already shows the effect starting.
"""

from collections.abc import Callable
from dataclasses import dataclass

from plume.recipe.derived import Derived
from plume.recipe.schema import Recipe
from plume.sim.grid import Grid, make_grid
from plume.sim.step_cap import StepCap
from plume.sim.stepper import Stepper

Capture = Callable[[int, Grid], None]


@dataclass(frozen=True)
class StepLog:
    """How many steps each part of the run took, after the CFL cap."""

    warmup_steps: int
    steps_per_frame: tuple[int, ...]
    base_steps_per_frame: int
    base_warmup_steps: int

    @property
    def total_steps(self) -> int:
        return self.warmup_steps + sum(self.steps_per_frame)

    @property
    def added_steps(self) -> int:
        """Steps the CFL cap added over the recipe's substeps, warmup included."""
        base = self.base_warmup_steps + self.base_steps_per_frame * len(self.steps_per_frame)
        return self.total_steps - base


def simulate(recipe: Recipe, derived: Derived, device: str, capture: Capture) -> StepLog:
    """Runs the whole recipe, calling `capture(frame_index, grid)` once per frame, in order."""
    grid = make_grid(derived, recipe.domain.cell_m, recipe.domain.faces, recipe.domain.ambient_k, device)
    stepper = Stepper(grid, recipe)
    cap = StepCap(recipe)
    base_done = 0

    def run_block(base_steps: int, label: str) -> int:
        nonlocal base_done
        start_s = base_done * derived.dt_s
        length_s = base_steps * derived.dt_s
        steps = cap.plan(grid, start_s, length_s, base_steps, label).steps
        for index in range(steps):
            if steps == base_steps:  # the cap did not bind: exactly the uncapped loop's times
                stepper.step((base_done + index) * derived.dt_s, derived.dt_s)
            else:
                stepper.step(start_s + index * length_s / steps, length_s / steps)
        base_done += base_steps
        return steps

    warmup_steps = 0
    remaining = derived.warmup_steps
    while remaining > 0:
        block = min(remaining, derived.steps_per_frame)
        warmup_steps += run_block(block, "warmup")
        remaining -= block
    frame_steps = []
    for frame in range(recipe.time.frames):
        frame_steps.append(run_block(derived.steps_per_frame, f"frame {frame}"))
        capture(frame, grid)
    return StepLog(warmup_steps, tuple(frame_steps), derived.steps_per_frame, derived.warmup_steps)
