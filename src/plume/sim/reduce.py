"""Deterministic sums of grid fields.

Each thread sums one row along z in a fixed order, then the host adds the rows in numpy float64. No
atomics, and the order never changes, so the same field always gives the same total on the same device.
"""

import numpy as np
import warp as wp


@wp.kernel
def row_sum_kernel(f: wp.array3d(dtype=float), rows: wp.array2d(dtype=float)):
    i, j = wp.tid()
    total = float(0.0)
    for k in range(f.shape[2]):
        total = total + f[i, j, k]
    rows[i, j] = total


class FieldSum:
    """Sums fields of one shape, reusing its row buffer."""

    def __init__(self, shape: tuple[int, int, int], device: str):
        self.rows = wp.zeros(shape[:2], dtype=float, device=device)
        self.device = device

    def __call__(self, field: wp.array) -> float:
        wp.launch(row_sum_kernel, dim=self.rows.shape, device=self.device, inputs=[field, self.rows])
        return float(self.rows.numpy().astype(np.float64).sum())


@wp.kernel
def scale_kernel(f: wp.array3d(dtype=float), factor: float):
    i, j, k = wp.tid()
    f[i, j, k] = f[i, j, k] * factor


@wp.kernel
def outflow_kernel(smoke: wp.array3d(dtype=float), component: wp.array3d(dtype=float), axis: int, high: int,
                   dt_over_cell: float, plane: wp.array2d(dtype=float)):
    """Smoke leaving through one face of the domain in one step, per boundary cell, in cell volumes."""
    p, q = wp.tid()
    n = smoke.shape[axis]
    cell = wp.vec3i(0, 0, 0)
    face = wp.vec3i(0, 0, 0)
    a = (axis + 1) % 3
    b = (axis + 2) % 3
    cell[a] = p
    cell[b] = q
    face[a] = p
    face[b] = q
    outward = float(0.0)
    if high == 1:
        cell[axis] = n - 1
        face[axis] = n
        outward = component[face[0], face[1], face[2]]
    else:
        outward = -component[face[0], face[1], face[2]]
    plane[p, q] = smoke[cell[0], cell[1], cell[2]] * wp.max(outward, 0.0) * dt_over_cell
