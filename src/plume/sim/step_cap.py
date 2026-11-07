"""The CFL cap (D10): enough steps that the fastest gas crosses at most `max_cells_per_step` cells per step.

Advection traces back along the flow; a step that carries gas many cells at once skips over the cells in
between and smears or tears what it carries. Before each block of steps (one frame's worth, or a piece of
warmup) the cap measures the fastest speed and splits the block into more, shorter steps when needed.

The fastest speed is the larger of the grid's fastest face velocity (copied to the host and reduced in
numpy float64, so it is deterministic) and the fastest emitter active during the block, since an emitter
sets its velocity the moment the block starts.
"""

import math
from dataclasses import dataclass

import numpy as np

from plume.recipe.errors import RecipeError
from plume.recipe.schema import Recipe
from plume.sim.grid import Grid


@dataclass(frozen=True)
class StepPlan:
    steps: int
    speed_mps: float


class StepCap:
    def __init__(self, recipe: Recipe):
        self.cell_m = recipe.domain.cell_m
        self.max_cells = recipe.solver.max_cells_per_step
        self.max_substeps = recipe.solver.max_substeps
        # An emitter's fastest component (outward mode: its full speed, along some axis at the extreme).
        self.emitters = [(e.start_s, e.end_s, _emitter_speed(e.velocity_mps, e.velocity_mode))
                         for e in recipe.emitter]

    def plan(self, grid: Grid, start_s: float, length_s: float, base_steps: int, label: str) -> StepPlan:
        """Steps for the block from `start_s` lasting `length_s`, at least `base_steps`."""
        speed = max(self.grid_speed(grid), self.emitter_speed(start_s, start_s + length_s))
        needed = math.ceil(speed * length_s / (self.max_cells * self.cell_m))
        steps = max(base_steps, needed)
        if steps > max(self.max_substeps, base_steps):
            raise RecipeError(
                f"{label} needs {steps} steps to keep the fastest gas ({speed:.3f} m/s) within "
                f"solver.max_cells_per_step ({self.max_cells}); solver.max_substeps is {self.max_substeps}. "
                f"Raise it, or slow the gas (emitter velocity, buoyancy, turbulence, drag)")
        return StepPlan(steps, speed)

    @staticmethod
    def grid_speed(grid: Grid) -> float:
        """The fastest face velocity component, in m/s. Each component moves gas along its own axis, so
        the largest one bounds how many cells a step crosses on any axis."""
        return max(float(np.abs(field.data.numpy().astype(np.float64)).max()) for field in grid.velocity_fields())

    def emitter_speed(self, start_s: float, end_s: float) -> float:
        speeds = [speed for begin, finish, speed in self.emitters if begin < end_s and finish > start_s]
        return max(speeds, default=0.0)


def _emitter_speed(velocity_mps: tuple[float, float, float], mode: str) -> float:
    velocity = np.asarray(velocity_mps, dtype=np.float64)
    if mode == "outward":
        return float(np.linalg.norm(velocity))
    return float(np.abs(velocity).max())
