"""Vorticity confinement (Fedkiw, Stam and Jensen 2001): puts back the small swirls that a coarse grid and
its interpolation smear out.

Each cell's spin is the curl of the velocity. Confinement pushes the gas around the cells that spin
fastest, along `N x curl`, where `N` points toward faster spin. The push is `strength * cell_m * (N x curl)`:
it grows with the cell size, so a coarse preview gets back about as much swirl as it lost (D30).

Four passes, each a gather: velocity at cell centers, curl at cell centers, the push at cell centers, then
each face adds the average push of the two cells beside it.
"""

import warp as wp

from plume.sim.grid import Grid, GridInfo


@wp.kernel
def center_velocity_kernel(u: wp.array3d(dtype=float), v: wp.array3d(dtype=float), w: wp.array3d(dtype=float),
                           center: wp.array3d(dtype=wp.vec3)):
    i, j, k = wp.tid()
    center[i, j, k] = wp.vec3(0.5 * (u[i, j, k] + u[i + 1, j, k]), 0.5 * (v[i, j, k] + v[i, j + 1, k]),
                              0.5 * (w[i, j, k] + w[i, j, k + 1]))


@wp.func
def central_difference(f: wp.array3d(dtype=wp.vec3), cell: wp.vec3i, axis: int, info: GridInfo) -> wp.vec3:
    """d f / d axis at a cell center, one-sided at the domain's edge (per meter)."""
    lo = cell
    hi = cell
    lo[axis] = wp.max(cell[axis] - 1, 0)
    hi[axis] = wp.min(cell[axis] + 1, info.dims[axis] - 1)
    span = float(hi[axis] - lo[axis])
    if span == 0.0:
        return wp.vec3(0.0, 0.0, 0.0)
    return (f[hi[0], hi[1], hi[2]] - f[lo[0], lo[1], lo[2]]) / (span * info.cell_m)


@wp.kernel
def curl_kernel(center: wp.array3d(dtype=wp.vec3), curl: wp.array3d(dtype=wp.vec3), info: GridInfo):
    i, j, k = wp.tid()
    cell = wp.vec3i(i, j, k)
    d_dx = central_difference(center, cell, 0, info)
    d_dy = central_difference(center, cell, 1, info)
    d_dz = central_difference(center, cell, 2, info)
    curl[i, j, k] = wp.vec3(d_dy[2] - d_dz[1], d_dz[0] - d_dx[2], d_dx[1] - d_dy[0])


@wp.func
def spin_at(curl: wp.array3d(dtype=wp.vec3), cell: wp.vec3i) -> float:
    return wp.length(curl[cell[0], cell[1], cell[2]])


@wp.kernel
def confinement_push_kernel(curl: wp.array3d(dtype=wp.vec3), push: wp.array3d(dtype=wp.vec3), info: GridInfo,
                            strength: float):
    i, j, k = wp.tid()
    cell = wp.vec3i(i, j, k)
    toward_spin = wp.vec3(0.0, 0.0, 0.0)
    for axis in range(3):
        lo = cell
        hi = cell
        lo[axis] = wp.max(cell[axis] - 1, 0)
        hi[axis] = wp.min(cell[axis] + 1, info.dims[axis] - 1)
        span = float(hi[axis] - lo[axis])
        if span > 0.0:
            toward_spin[axis] = (spin_at(curl, hi) - spin_at(curl, lo)) / (span * info.cell_m)
    length = wp.length(toward_spin)
    if length < 1.0e-12:
        push[i, j, k] = wp.vec3(0.0, 0.0, 0.0)
        return
    push[i, j, k] = strength * info.cell_m * wp.cross(toward_spin / length, curl[i, j, k])


@wp.kernel
def add_face_push_kernel(f: wp.array3d(dtype=float), push: wp.array3d(dtype=wp.vec3), axis: int, info: GridInfo,
                         dt: float):
    i, j, k = wp.tid()
    face = wp.vec3i(i, j, k)
    below = face
    above = face
    below[axis] = wp.max(face[axis] - 1, 0)
    above[axis] = wp.min(face[axis], info.dims[axis] - 1)
    average = 0.5 * (push[below[0], below[1], below[2]][axis] + push[above[0], above[1], above[2]][axis])
    f[i, j, k] = f[i, j, k] + average * dt


class VorticityConfinement:
    """Scratch fields for confinement on one grid, allocated once per run."""

    def __init__(self, grid: Grid):
        self.center = wp.zeros(grid.cells, dtype=wp.vec3, device=grid.device)
        self.curl = wp.zeros(grid.cells, dtype=wp.vec3, device=grid.device)
        self.push = wp.zeros(grid.cells, dtype=wp.vec3, device=grid.device)

    def apply(self, grid: Grid, strength: float, dt: float) -> None:
        """Adds `strength * cell_m * (N x curl) * dt` to the face velocities; nothing when strength is 0."""
        if strength == 0.0:
            return
        u, v, w = (field.data for field in grid.velocity_fields())
        wp.launch(center_velocity_kernel, dim=grid.cells, device=grid.device, inputs=[u, v, w, self.center])
        self.compute_curl(grid)
        wp.launch(confinement_push_kernel, dim=grid.cells, device=grid.device,
                  inputs=[self.curl, self.push, grid.info, strength])
        for axis, component in enumerate((u, v, w)):
            wp.launch(add_face_push_kernel, dim=component.shape, device=grid.device,
                      inputs=[component, self.push, axis, grid.info, dt])

    def compute_curl(self, grid: Grid) -> wp.array:
        """Fills and returns the curl at cell centers from `self.center` (call after the center pass)."""
        wp.launch(curl_kernel, dim=grid.cells, device=grid.device, inputs=[self.center, self.curl, grid.info])
        return self.curl

    def measure_curl(self, grid: Grid) -> wp.array:
        """The curl of the grid's current velocity at cell centers (for tests and reports)."""
        u, v, w = (field.data for field in grid.velocity_fields())
        wp.launch(center_velocity_kernel, dim=grid.cells, device=grid.device, inputs=[u, v, w, self.center])
        return self.compute_curl(grid)
