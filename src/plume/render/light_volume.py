"""The light volume: the share of the key light that reaches each cell through the smoke between it and
the light, for the shade layout's self-shadowing.

One thread per cell marches from the cell's center toward the light in half-cell steps until the ray
leaves the domain, sums the smoke it passes (trilinear samples) and writes
`exp(-opacity_per_density * column_density_m)`. The step count is fixed by the ray's length inside the
box, and each thread writes only its own cell, so the result is the same bytes on every run. Nothing
outside the domain casts a shadow.
"""

import numpy as np
import warp as wp

from plume.render.raymarch import slab_range
from plume.sim.sample import sample_index_space


@wp.kernel
def light_volume_kernel(smoke: wp.array3d(dtype=float), toward_light: wp.vec3, cell_m: float,
                        opacity_per_density: float, light: wp.array3d(dtype=float)):
    i, j, k = wp.tid()
    half = wp.vec3(0.5, 0.5, 0.5)  # cell centers sit half a cell in from their index
    start = wp.vec3(float(i), float(j), float(k)) + half  # cell units from the domain's minimum corner
    box_max = wp.vec3(float(smoke.shape[0]), float(smoke.shape[1]), float(smoke.shape[2]))
    length = slab_range(start, toward_light, wp.vec3(0.0, 0.0, 0.0), box_max)[1]
    steps = int(wp.ceil(length / 0.5))
    column_cells = float(0.0)
    if steps > 0:
        step = length / float(steps)
        for s in range(steps):
            position = start + toward_light * ((float(s) + 0.5) * step)
            column_cells = column_cells + wp.max(sample_index_space(smoke, position - half), 0.0) * step
    light[i, j, k] = wp.exp(-opacity_per_density * column_cells * cell_m)


class LightVolume:
    """Owns the light array and fills it once per rendered frame."""

    def __init__(self, cells: tuple[int, int, int], toward_light_world: np.ndarray, opacity_per_density: float,
                 device: str):
        self.device = device
        direction = np.asarray(toward_light_world, dtype=np.float64)
        self.toward_light = wp.vec3(*(direction / np.linalg.norm(direction)))
        self.opacity_per_density = opacity_per_density
        self.light = wp.zeros(cells, dtype=float, device=device)

    def compute(self, smoke: wp.array, cell_m: float) -> wp.array:
        """The light reaching each cell of a smoke field (cells of `cell_m`), 0 to 1."""
        wp.launch(light_volume_kernel, dim=smoke.shape, device=self.device,
                  inputs=[smoke, self.toward_light, cell_m, self.opacity_per_density, self.light])
        return self.light
