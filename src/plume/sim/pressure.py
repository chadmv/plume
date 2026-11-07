"""Pressure projection: removes the part of the velocity that compresses or expands the gas.

Solves `laplacian(q) = divergence(u)` for a scaled pressure `q`, then subtracts `gradient(q)` from the
face velocities. Closed faces are walls (zero normal velocity, no pressure across them); open faces see
zero pressure just outside, so gas flows through them freely.

Slice 1 solves with a fixed number of red-black Gauss-Seidel sweeps with over-relaxation, starting from
the previous step's pressure. Slice 2 replaces the solve with multigrid behind `project`.
"""

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
def neighbor_term(q: wp.array3d(dtype=float), cell: wp.vec3i, axis: int, step: int, info: GridInfo) -> wp.vec2:
    """A neighbor's (pressure, counts) contribution: inside cells count, open-face ghosts count as 0."""
    n = cell
    n[axis] = n[axis] + step
    if n[axis] >= 0 and n[axis] < info.dims[axis]:
        return wp.vec2(q[n[0], n[1], n[2]], 1.0)
    if step < 0 and info.open_lo[axis] == 1:
        return wp.vec2(0.0, 1.0)
    if step > 0 and info.open_hi[axis] == 1:
        return wp.vec2(0.0, 1.0)
    return wp.vec2(0.0, 0.0)


@wp.kernel
def red_black_sweep_kernel(q: wp.array3d(dtype=float), divergence: wp.array3d(dtype=float), info: GridInfo,
                           color: int, relaxation: float):
    i, j, k = wp.tid()
    if (i + j + k) % 2 != color:
        return
    cell = wp.vec3i(i, j, k)
    total = wp.vec2(0.0, 0.0)
    for axis in range(3):
        total = total + neighbor_term(q, cell, axis, -1, info) + neighbor_term(q, cell, axis, 1, info)
    if total[1] == 0.0:
        return
    target = (total[0] - info.cell_m * info.cell_m * divergence[i, j, k]) / total[1]
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


def project(grid: Grid, iterations: int) -> None:
    """Makes the face velocities divergence-free (to the solver's accuracy) and walls impermeable."""
    velocity = [field.data for field in grid.velocity_fields()]
    for axis, component in enumerate(velocity):
        wp.launch(zero_closed_faces_kernel, dim=component.shape, device=grid.device,
                  inputs=[component, axis, grid.info])
    compute_divergence(grid)
    for _ in range(iterations):
        for color in (0, 1):
            wp.launch(red_black_sweep_kernel, dim=grid.cells, device=grid.device,
                      inputs=[grid.pressure, grid.divergence, grid.info, color, RELAXATION])
    for axis, component in enumerate(velocity):
        wp.launch(subtract_gradient_kernel, dim=component.shape, device=grid.device,
                  inputs=[component, grid.pressure, axis, grid.info])


def compute_divergence(grid: Grid) -> wp.array:
    """Fills and returns `grid.divergence` from the current face velocities."""
    u, v, w = (field.data for field in grid.velocity_fields())
    wp.launch(divergence_kernel, dim=grid.cells, device=grid.device,
              inputs=[u, v, w, grid.divergence, grid.info])
    return grid.divergence
