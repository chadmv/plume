"""Keeping advection from adding or losing smoke (the T2.6 decision).

Clamped MacCormack is not conservative. Measured on the smoke puff with no dissipation, smoke grew by 30
percent over 2.4 s, and with turbulence and confinement by 68 percent on a 0.031 m grid and 109 percent on
the 0.052 m preview grid: clamping the correction's dips at wispy edges adds smoke, more so on coarse
grids, so a preview and its final run drifted apart. Plain semi-Lagrangian loses smoke instead (about 15
percent on a small, sharp puff).

So after each smoke advection the field is scaled to the total it should have: the total before the step
minus what flowed out through open faces (upwind smoke times outward face speed). Inflow brings in the
outside value, 0. The scale is one number for the whole grid, so the shape MacCormack gives is kept.
"""

import numpy as np
import warp as wp

from plume.sim.grid import Grid
from plume.sim.reduce import FieldSum, outflow_kernel, scale_kernel


class SmokeBudget:
    """Scratch buffers for one grid's smoke budget."""

    def __init__(self, grid: Grid):
        self.field_sum = FieldSum(grid.cells, grid.device)
        nx, ny, nz = grid.cells
        # Face planes per axis, indexed as the kernel's (axis + 1, axis + 2) cell indices.
        self.planes = [wp.zeros((ny, nz), dtype=float, device=grid.device),
                       wp.zeros((nz, nx), dtype=float, device=grid.device),
                       wp.zeros((nx, ny), dtype=float, device=grid.device)]

    def expected_after(self, grid: Grid, dt: float) -> float:
        """The total smoke should have after advecting the current field for `dt`, in cell volumes."""
        smoke = grid.smoke.data
        total = self.field_sum(smoke)
        open_sides = ((grid.info.open_lo, 0), (grid.info.open_hi, 1))
        for axis, field in enumerate(grid.velocity_fields()):
            for flags, high in open_sides:
                if flags[axis] == 1:
                    plane = self.planes[axis]
                    wp.launch(outflow_kernel, dim=plane.shape, device=grid.device,
                              inputs=[smoke, field.data, axis, high, dt / grid.info.cell_m, plane])
                    total -= float(plane.numpy().astype(np.float64).sum())
        return max(total, 0.0)

    def rescale(self, grid: Grid, target: float) -> None:
        """Scales the freshly advected smoke (`grid.smoke.next`) to `target`."""
        actual = self.field_sum(grid.smoke.next)
        if actual > 0.0:
            wp.launch(scale_kernel, dim=grid.cells, device=grid.device,
                      inputs=[grid.smoke.next, float(target / actual)])
