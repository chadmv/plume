"""Pressure projection: removes the part of the velocity that compresses or expands the gas.

Solves `laplacian(q) = divergence(u)` for a scaled pressure `q`, then subtracts `gradient(q)` from the
face velocities. Closed faces are walls (zero normal velocity, no pressure across them); open faces see
zero pressure just outside, so gas flows through them freely.

The solve itself is passed in: `GaussSeidel` here (slice 1's fixed count of red-black sweeps with
over-relaxation) or `Multigrid` in `sim/multigrid.py`. Both start from the previous step's pressure.
"""

from typing import Protocol

import warp as wp

from plume.sim.grid import Grid, GridInfo

# Over-relaxation factor for the red-black sweeps; 1 is plain Gauss-Seidel, below 2 always converges.
RELAXATION = 1.5


@wp.kernel
def zero_closed_faces_kernel(f: wp.array3d(dtype=float), axis: int, info: GridInfo):
    i, j, k = wp.tid()
    index = wp.vec3i(i, j, k)[axis]
    if index == 0 and info.open_lo[axis] == 0:
        f[i, j, k] = 0.0
    if index == info.dims[axis] and info.open_hi[axis] == 0:
        f[i, j, k] = 0.0


@wp.kernel
def divergence_kernel(u: wp.array3d(dtype=float), v: wp.array3d(dtype=float), w: wp.array3d(dtype=float),
                      divergence: wp.array3d(dtype=float), info: GridInfo):
    i, j, k = wp.tid()
    flux = (u[i + 1, j, k] - u[i, j, k]) + (v[i, j + 1, k] - v[i, j, k]) + (w[i, j, k + 1] - w[i, j, k])
    divergence[i, j, k] = flux / info.cell_m


@wp.func
def cell_fill(info: GridInfo, axis: int, index: int) -> float:
    """The share of a cell's width along `axis` inside the domain: 1 except a coarse level's overhang."""
    if index == info.dims[axis] - 1:
        return info.fill_hi[axis]
    return 1.0


@wp.func
def cell_volume(info: GridInfo, cell: wp.vec3i) -> float:
    return cell_fill(info, 0, cell[0]) * cell_fill(info, 1, cell[1]) * cell_fill(info, 2, cell[2])


@wp.func
def neighbor_term(q: wp.array3d(dtype=float), cell: wp.vec3i, axis: int, step: int, info: GridInfo) -> wp.vec2:
    """A neighbor's (coupling times pressure, coupling): the shared face's area over the distance between
    the two pressure points, in cells. Open-face ghosts hold pressure 0; closed faces couple nothing.
    On the simulation grid every coupling is exactly 1."""
    area = float(1.0)
    for other in range(3):
        if other != axis:
            area = area * cell_fill(info, other, cell[other])
    own = cell_fill(info, axis, cell[axis])
    n = cell
    n[axis] = n[axis] + step
    if n[axis] >= 0 and n[axis] < info.dims[axis]:
        coupling = area / (0.5 * (own + cell_fill(info, axis, n[axis])))
        return wp.vec2(coupling * q[n[0], n[1], n[2]], coupling)
    if (step < 0 and info.open_lo[axis] == 1) or (step > 0 and info.open_hi[axis] == 1):
        return wp.vec2(0.0, area / (0.5 * own + info.ghost_gap))
    return wp.vec2(0.0, 0.0)


@wp.func
def neighbor_sum(q: wp.array3d(dtype=float), cell: wp.vec3i, info: GridInfo) -> wp.vec2:
    total = wp.vec2(0.0, 0.0)
    for axis in range(3):
        total = total + neighbor_term(q, cell, axis, -1, info) + neighbor_term(q, cell, axis, 1, info)
    return total


@wp.kernel
def red_black_sweep_kernel(q: wp.array3d(dtype=float), rhs: wp.array3d(dtype=float), info: GridInfo,
                           color: int, relaxation: float):
    i, j, k = wp.tid()
    if (i + j + k) % 2 != color:
        return
    cell = wp.vec3i(i, j, k)
    total = neighbor_sum(q, cell, info)
    if total[1] == 0.0:
        return
    source = cell_volume(info, cell) * info.cell_m * info.cell_m * rhs[i, j, k]
    target = (total[0] - source) / total[1]
    q[i, j, k] = q[i, j, k] + relaxation * (target - q[i, j, k])


@wp.kernel
def subtract_gradient_kernel(f: wp.array3d(dtype=float), q: wp.array3d(dtype=float), axis: int,
                             info: GridInfo):
    i, j, k = wp.tid()
    face = wp.vec3i(i, j, k)
    index = face[axis]
    below = face
    below[axis] = index - 1
    q_above = 0.0
    q_below = 0.0
    if index == 0:
        if info.open_lo[axis] == 0:
            return
        q_above = q[i, j, k]
    elif index == info.dims[axis]:
        if info.open_hi[axis] == 0:
            return
        q_below = q[below[0], below[1], below[2]]
    else:
        q_above = q[i, j, k]
        q_below = q[below[0], below[1], below[2]]
    f[i, j, k] = f[i, j, k] - (q_above - q_below) / info.cell_m


class PressureSolve(Protocol):
    def __call__(self, grid: Grid) -> None:
        """Improves `grid.pressure` toward the solution of `laplacian(q) = grid.divergence`."""


class GaussSeidel:
    """A fixed number of red-black Gauss-Seidel sweeps with over-relaxation."""

    def __init__(self, iterations: int):
        self.iterations = iterations

    def __call__(self, grid: Grid) -> None:
        red_black_sweeps(grid.pressure, grid.divergence, grid.info, grid.cells, grid.device, self.iterations,
                         RELAXATION)


def red_black_sweeps(q: wp.array, rhs: wp.array, info: GridInfo, cells: tuple[int, int, int], device: str,
                     sweeps: int, relaxation: float) -> None:
    """`sweeps` red-black sweeps of `laplacian(q) = rhs` on the grid `info` describes."""
    for _ in range(sweeps):
        for color in (0, 1):
            wp.launch(red_black_sweep_kernel, dim=cells, device=device,
                      inputs=[q, rhs, info, color, relaxation])


def project(grid: Grid, solve: PressureSolve) -> None:
    """Makes the face velocities divergence-free (to the solver's accuracy) and walls impermeable."""
    velocity = [field.data for field in grid.velocity_fields()]
    for axis, component in enumerate(velocity):
        wp.launch(zero_closed_faces_kernel, dim=component.shape, device=grid.device,
                  inputs=[component, axis, grid.info])
    compute_divergence(grid)
    solve(grid)
    for axis, component in enumerate(velocity):
        wp.launch(subtract_gradient_kernel, dim=component.shape, device=grid.device,
                  inputs=[component, grid.pressure, axis, grid.info])


def compute_divergence(grid: Grid) -> wp.array:
    """Fills and returns `grid.divergence` from the current face velocities."""
    u, v, w = (field.data for field in grid.velocity_fields())
    wp.launch(divergence_kernel, dim=grid.cells, device=grid.device,
              inputs=[u, v, w, grid.divergence, grid.info])
    return grid.divergence
