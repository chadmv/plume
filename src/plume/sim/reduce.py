"""Deterministic sums of grid fields.

Each thread sums one line along x in a fixed order (neighboring threads read neighboring memory), then
the host adds the lines in numpy float64. No atomics, and the order never changes, so the same fields
always give the same totals on the same device.
"""

import numpy as np
import warp as wp


@wp.kernel
def line_sums_kernel(a: wp.array3d(dtype=float), b: wp.array3d(dtype=float), c: wp.array3d(dtype=float),
                     lines: wp.array3d(dtype=float)):
    j, k = wp.tid()
    total_a = float(0.0)
    total_b = float(0.0)
    total_c = float(0.0)
    for i in range(a.shape[0]):
        total_a = total_a + a[i, j, k]
        total_b = total_b + b[i, j, k]
        total_c = total_c + c[i, j, k]
    lines[0, j, k] = total_a
    lines[1, j, k] = total_b
    lines[2, j, k] = total_c


class TripleSum:
    """Totals of three same-shaped fields, with one copy to the host."""

    def __init__(self, shape: tuple[int, int, int], device: str):
        self.lines = wp.zeros((3, shape[1], shape[2]), dtype=float, device=device)
        self.device = device

    def __call__(self, a: wp.array, b: wp.array, c: wp.array) -> tuple[float, float, float]:
        wp.launch(line_sums_kernel, dim=self.lines.shape[1:], device=self.device, inputs=[a, b, c, self.lines])
        totals = self.lines.numpy().astype(np.float64).sum(axis=(1, 2))
        return float(totals[0]), float(totals[1]), float(totals[2])
