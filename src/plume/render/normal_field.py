"""The smoke surface direction field: the gradient of a Gaussian-blurred copy of the smoke.

Blurring first makes the normals describe the smoke's soft overall form rather than cell-sized noise.
"""

import math

import numpy as np
import warp as wp


@wp.kernel
def blur_axis_kernel(src: wp.array3d(dtype=float), dst: wp.array3d(dtype=float), weights: wp.array(dtype=float),
                     radius: int, axis: int):
    i, j, k = wp.tid()
    cell = wp.vec3i(i, j, k)
    total = float(0.0)
    for offset in range(-radius, radius + 1):
        n = cell
        n[axis] = wp.clamp(cell[axis] + offset, 0, src.shape[axis] - 1)
        total = total + weights[offset + radius] * src[n[0], n[1], n[2]]
    dst[i, j, k] = total


@wp.kernel
def gradient_kernel(src: wp.array3d(dtype=float), gradient: wp.array3d(dtype=wp.vec3)):
    i, j, k = wp.tid()
    cell = wp.vec3i(i, j, k)
    result = wp.vec3(0.0, 0.0, 0.0)
    for axis in range(3):
        lo = cell
        hi = cell
        lo[axis] = wp.max(cell[axis] - 1, 0)
        hi[axis] = wp.min(cell[axis] + 1, src.shape[axis] - 1)
        span = float(hi[axis] - lo[axis])
        if span > 0.0:
            result[axis] = (src[hi[0], hi[1], hi[2]] - src[lo[0], lo[1], lo[2]]) / span
    gradient[i, j, k] = result


class NormalField:
    """Owns the scratch arrays and computes the blurred smoke gradient once per frame."""

    def __init__(self, cells: tuple[int, int, int], blur_cells: float, device: str):
        self.device = device
        self.blurred = wp.zeros(cells, dtype=float, device=device)
        self.scratch = wp.zeros(cells, dtype=float, device=device)
        self.gradient = wp.zeros(cells, dtype=wp.vec3, device=device)
        self.radius = math.ceil(3.0 * blur_cells) if blur_cells > 0 else 0
        self.weights = wp.array(_gaussian_weights(blur_cells, self.radius), dtype=float, device=device)

    def compute(self, smoke: wp.array) -> wp.array:
        """Returns the gradient (per cell) of the blurred smoke."""
        source = smoke
        targets = (self.blurred, self.scratch, self.blurred)
        for axis, target in enumerate(targets):
            wp.launch(blur_axis_kernel, dim=smoke.shape, device=self.device,
                      inputs=[source, target, self.weights, self.radius, axis])
            source = target
        wp.launch(gradient_kernel, dim=smoke.shape, device=self.device, inputs=[source, self.gradient])
        return self.gradient


def _gaussian_weights(sigma: float, radius: int) -> np.ndarray:
    if radius == 0:
        return np.ones(1, dtype=np.float32)
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    weights = np.exp(-offsets**2 / (2.0 * sigma**2))
    return (weights / weights.sum()).astype(np.float32)
