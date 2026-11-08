"""The soften pass: a light Gaussian blur on every channel, then (normal layout) normals made unit length
again."""

import math

import numpy as np

from plume.recipe.schema import NORMAL_LAYOUT
from plume.render.raw_frame import NORMAL_X, NORMAL_Z


def soften(frame: np.ndarray, sigma_px: float, channels: str) -> np.ndarray:
    """Blurs all channels of a (size, size, 5) frame by `sigma_px`; in the normal layout, renormalizes
    its normals."""
    result = blur(frame, sigma_px)
    return _renormalize(result) if channels == NORMAL_LAYOUT else result


def blur(image: np.ndarray, sigma_px: float) -> np.ndarray:
    """A Gaussian blur over the first two axes, edges extended; `sigma_px` 0 returns the image."""
    if sigma_px <= 0.0:
        return image
    weights = _gaussian(sigma_px)
    return _blur_axis(_blur_axis(image, weights, axis=0), weights, axis=1)


def _gaussian(sigma: float) -> np.ndarray:
    radius = math.ceil(3.0 * sigma)
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    weights = np.exp(-offsets**2 / (2.0 * sigma**2))
    return weights / weights.sum()


def _blur_axis(image: np.ndarray, weights: np.ndarray, axis: int) -> np.ndarray:
    radius = len(weights) // 2
    pad = [(0, 0)] * image.ndim
    pad[axis] = (radius, radius)
    padded = np.pad(image, pad, mode="edge")
    size = image.shape[axis]
    result = np.zeros_like(image)
    for offset, weight in enumerate(weights):
        result += weight * np.take(padded, np.arange(offset, offset + size), axis=axis)
    return result


def _renormalize(frame: np.ndarray) -> np.ndarray:
    result = frame.copy()
    normal = result[..., NORMAL_X:NORMAL_Z + 1]
    normal[..., 2] = np.abs(normal[..., 2])
    length = np.linalg.norm(normal, axis=-1, keepdims=True)
    facing = np.array([0.0, 0.0, 1.0])
    result[..., NORMAL_X:NORMAL_Z + 1] = np.where(length > 1e-6, normal / np.maximum(length, 1e-6), facing)
    return result
