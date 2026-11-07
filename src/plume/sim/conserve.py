"""Keeping clamped MacCormack from adding smoke (the T2.6 decision).

Clamped MacCormack is not conservative. Measured on the smoke puff with no dissipation, smoke grew by 30
percent over 2.4 s, and with turbulence and confinement by 68 percent on a 0.031 m grid and 109 percent on
the 0.052 m preview grid: clamping the correction's dips at wispy edges adds smoke, more so on coarse
grids, so a preview and its final run drifted apart.

After each smoke advection the MacCormack total is held between two bounds, by scaling the whole field
by one number (so the shape MacCormack gives is kept):

- at most the total before the step, so advection never creates smoke;
- at least the plain semi-Lagrangian total (MacCormack's first pass), which carries smoke out through open
  faces the same way the scheme does, so smoke leaving the domain is never over-counted.

A first version budgeted "before minus estimated outflow"; a review found the estimate removed far more
than left through an open top (by frame 2 a hot puff held 0.16 below the face against 7.3 in a taller
domain), so the bounds use only totals the scheme itself produced. Plain semi-Lagrangian still loses some
smoke on small, sharp puffs (about 11 percent over 40 steps on the closed-box test).
"""

import warp as wp

from plume.sim.grid import Grid
from plume.sim.reduce import TripleSum


@wp.kernel
def scale_kernel(f: wp.array3d(dtype=float), factor: float):
    i, j, k = wp.tid()
    f[i, j, k] = f[i, j, k] * factor


def held_total(before: float, semi_lagrangian: float, maccormack: float) -> float:
    """MacCormack's total held to the scheme's own bounds (see the module docstring)."""
    return max(semi_lagrangian, min(maccormack, before))


class SmokeBudget:
    """Scratch for one grid's smoke totals."""

    def __init__(self, grid: Grid):
        self.sums = TripleSum(grid.cells, grid.device)
        self.last_factor = 1.0

    def hold(self, grid: Grid) -> None:
        """Call after advecting smoke and before swapping: rescales `grid.smoke.next` into its bounds."""
        smoke = grid.smoke
        before, semi_lagrangian, maccormack = self.sums(smoke.data, smoke.hat, smoke.next)
        target = held_total(before, semi_lagrangian, maccormack)
        self.last_factor = target / maccormack if maccormack > 0.0 else 1.0
        if self.last_factor != 1.0:
            wp.launch(scale_kernel, dim=grid.cells, device=grid.device, inputs=[smoke.next, self.last_factor])
