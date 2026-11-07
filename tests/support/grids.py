"""Small grids for solver tests, built without a recipe."""

import numpy as np
import warp as wp

from plume.recipe.derived import Derived
from plume.recipe.schema import FaceSettings
from plume.sim.grid import Grid, make_grid

ALL_CLOSED = FaceSettings(bottom="closed", top="closed", left="closed", right="closed", back="closed",
                          front="closed")


def small_grid(device: str, cells=(16, 16, 16), cell_m=0.1, faces: FaceSettings = ALL_CLOSED,
               ambient_k=293.0) -> Grid:
    size = tuple(n * cell_m for n in cells)
    derived = Derived(cells=cells, size_m=size, domain_min_m=(-size[0] / 2, 0.0, -size[2] / 2), fps=20.0,
                      dt_s=1 / 60, warmup_steps=0, steps_per_frame=3)
    return make_grid(derived, cell_m, faces, ambient_k, device)


def fill(array: wp.array, values: np.ndarray) -> None:
    array.assign(wp.array(values.astype(np.float32), device=array.device))


def blob(shape, center, radius) -> np.ndarray:
    idx = np.indices(shape).astype(np.float64) + 0.5
    dist2 = sum((idx[a] - center[a]) ** 2 for a in range(3))
    return np.exp(-dist2 / (2 * radius**2))
