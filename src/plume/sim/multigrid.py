"""Geometric multigrid for the pressure solve: a fixed number of V-cycles per projection (D7).

Gauss-Seidel sweeps remove short-wavelength error quickly and long-wavelength error very slowly. Multigrid
hands the long-wavelength part to coarser copies of the grid, where it is short again: each level halves
the cell count per axis (rounding up) and doubles the cell size, down to a few cells. One V-cycle smooths
on the way down, solves the coarsest level with a fixed number of sweeps, and adds each level's correction
on the way back up, smoothing again.

Cell-centered finite volumes, with averaging restriction and trilinear prolongation. Coarse levels keep the
fine grid's open and closed faces; on an axis whose cell count does not halve evenly, a coarse level's last cell
overhangs the domain, and the stencil weighs that cell by the share of it inside (`coarse_geometry`).
Without that, odd-sized grids (the 80 x 100 x 80 puff halves to 5 and 13) converged about 8 times
slower. Every kernel gathers, and every count is fixed, so results are deterministic.
"""

from dataclasses import dataclass

import warp as wp

from plume.sim.grid import Grid, GridInfo
from plume.sim.pressure import cell_volume, neighbor_sum, red_black_sweeps
from plume.sim.sample import sample_index_space

# Stop coarsening once any axis is this short, or after this many levels.
MIN_LEVEL_CELLS = 2
MAX_LEVELS = 8
# The coarsest level is small, so a fixed number of over-relaxed sweeps solves it well.
COARSEST_SWEEPS = 20
COARSEST_RELAXATION = 1.5
SMOOTHING_RELAXATION = 1.0


@wp.kernel
def residual_kernel(q: wp.array3d(dtype=float), rhs: wp.array3d(dtype=float), residual: wp.array3d(dtype=float),
                    info: GridInfo):
    i, j, k = wp.tid()
    cell = wp.vec3i(i, j, k)
    total = neighbor_sum(q, cell, info)
    scale = cell_volume(info, cell) * info.cell_m * info.cell_m
    residual[i, j, k] = rhs[i, j, k] - (total[0] - total[1] * q[i, j, k]) / scale


@wp.kernel
def restrict_kernel(fine: wp.array3d(dtype=float), coarse: wp.array3d(dtype=float)):
    i, j, k = wp.tid()
    total = float(0.0)
    count = float(0.0)
    for di in range(2):
        for dj in range(2):
            for dk in range(2):
                fi = 2 * i + di
                fj = 2 * j + dj
                fk = 2 * k + dk
                if fi < fine.shape[0] and fj < fine.shape[1] and fk < fine.shape[2]:
                    total = total + fine[fi, fj, fk]
                    count = count + 1.0
    coarse[i, j, k] = total / count


@wp.kernel
def prolong_add_kernel(coarse: wp.array3d(dtype=float), fine: wp.array3d(dtype=float)):
    i, j, k = wp.tid()
    # Fine cell centers sit at (i + 0.5) fine cells; in coarse index space that is i / 2 - 0.25.
    g = wp.vec3(float(i), float(j), float(k)) * 0.5 - wp.vec3(0.25, 0.25, 0.25)
    fine[i, j, k] = fine[i, j, k] + sample_index_space(coarse, g)


@dataclass
class Level:
    info: GridInfo
    cells: tuple[int, int, int]
    q: wp.array
    rhs: wp.array
    residual: wp.array


def coarse_cells(cells: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple((n + 1) // 2 for n in cells)


def coarse_geometry(top_cells: tuple[int, int, int], cells: tuple[int, int, int],
                    level: int) -> tuple[wp.vec3, float]:
    """Where a coarse level's cells sit against the simulation grid's domain.

    A level `level` steps down has cells `2 ** level` top cells wide. On an axis whose top count is not a
    multiple of that, the last coarse cell overhangs the domain; `fill_hi` is the share inside it. The top
    grid holds pressure 0 half a top cell beyond each open face, which is `ghost_gap` coarse cells.
    """
    scale = 2.0 ** level
    fill = [top_n / scale - (n - 1) for top_n, n in zip(top_cells, cells)]
    return wp.vec3(*fill), 0.5 / scale


class Multigrid:
    """`cycles` V-cycles per solve, with `sweeps` smoothing sweeps before and after each correction."""

    def __init__(self, grid: Grid, cycles: int, sweeps: int):
        self.cycles = cycles
        self.sweeps = sweeps
        self.device = grid.device
        self.levels = self._build_levels(grid)

    def _build_levels(self, grid: Grid) -> list[Level]:
        top = Level(grid.info, grid.cells, grid.pressure, grid.divergence,
                    wp.zeros(grid.cells, dtype=float, device=grid.device))
        levels = [top]
        while min(levels[-1].cells) > MIN_LEVEL_CELLS and len(levels) < MAX_LEVELS:
            above = levels[-1]
            cells = coarse_cells(above.cells)
            info = GridInfo()
            info.dims = wp.vec3i(*cells)
            info.cell_m = above.info.cell_m * 2.0
            info.origin_m = above.info.origin_m
            info.open_lo = above.info.open_lo
            info.open_hi = above.info.open_hi
            info.fill_hi, info.ghost_gap = coarse_geometry(grid.cells, cells, len(levels))
            levels.append(Level(info, cells, *(wp.zeros(cells, dtype=float, device=self.device)
                                               for _ in range(3))))
        return levels

    def __call__(self, grid: Grid) -> None:
        self.levels[0].q = grid.pressure
        self.levels[0].rhs = grid.divergence
        for _ in range(self.cycles):
            self._v_cycle(0)

    def _v_cycle(self, index: int) -> None:
        level = self.levels[index]
        if index == len(self.levels) - 1:
            red_black_sweeps(level.q, level.rhs, level.info, level.cells, self.device, COARSEST_SWEEPS,
                             COARSEST_RELAXATION)
            return
        red_black_sweeps(level.q, level.rhs, level.info, level.cells, self.device, self.sweeps,
                         SMOOTHING_RELAXATION)
        wp.launch(residual_kernel, dim=level.cells, device=self.device,
                  inputs=[level.q, level.rhs, level.residual, level.info])
        coarse = self.levels[index + 1]
        wp.launch(restrict_kernel, dim=coarse.cells, device=self.device, inputs=[level.residual, coarse.rhs])
        coarse.q.zero_()
        self._v_cycle(index + 1)
        wp.launch(prolong_add_kernel, dim=level.cells, device=self.device, inputs=[coarse.q, level.q])
        red_black_sweeps(level.q, level.rhs, level.info, level.cells, self.device, self.sweeps,
                         SMOOTHING_RELAXATION)
