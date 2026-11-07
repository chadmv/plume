"""Dissipation: smoke fades and temperature relaxes toward ambient, both exponentially."""

import math

import warp as wp

from plume.sim.grid import Grid


@wp.kernel
def dissipate_kernel(smoke: wp.array3d(dtype=float), temperature: wp.array3d(dtype=float), smoke_keep: float,
                     heat_keep: float, ambient_k: float):
    i, j, k = wp.tid()
    smoke[i, j, k] = smoke[i, j, k] * smoke_keep
    temperature[i, j, k] = ambient_k + (temperature[i, j, k] - ambient_k) * heat_keep


def dissipate(grid: Grid, smoke_per_s: float, cooling_per_s: float, ambient_k: float, dt: float) -> None:
    """One step of exponential fading: smoke by `smoke_per_s`, heat toward ambient by `cooling_per_s`."""
    if smoke_per_s == 0.0 and cooling_per_s == 0.0:
        return
    wp.launch(dissipate_kernel, dim=grid.cells, device=grid.device,
              inputs=[grid.smoke.data, grid.temperature.data, math.exp(-smoke_per_s * dt),
                      math.exp(-cooling_per_s * dt), ambient_k])
