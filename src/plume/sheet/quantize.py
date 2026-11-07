"""Quantizing a finished float frame into the sheet's four 8-bit channels.

R = heat / divisor, G = thickness, B and A = camera-space normal x and y mapped from -1..1 to 0..255
(so a camera-facing normal reads 128, 128 and A = 255 faces up). All linear. Where a pixel is empty (R and
G both 0), B and A are exactly 128.
"""

import numpy as np

from plume.render.raw_frame import HEAT, NORMAL_X, NORMAL_Y, THICKNESS

FACING_BYTE = 128


def quantize(frame: np.ndarray, heat_divisor: float) -> np.ndarray:
    """A (size, size, 4) uint8 RGBA frame from a (size, size, 5) float frame."""
    heat = frame[..., HEAT] / heat_divisor if heat_divisor > 0.0 else np.zeros(frame.shape[:2])
    rgba = np.stack([
        _to_byte(heat),
        _to_byte(frame[..., THICKNESS]),
        _to_byte((frame[..., NORMAL_X] + 1.0) * 0.5),
        _to_byte((frame[..., NORMAL_Y] + 1.0) * 0.5),
    ], axis=-1)
    empty = (rgba[..., 0] == 0) & (rgba[..., 1] == 0)
    rgba[empty, 2] = FACING_BYTE
    rgba[empty, 3] = FACING_BYTE
    return rgba


def _to_byte(values: np.ndarray) -> np.ndarray:
    return np.clip(np.floor(values * 255.0 + 0.5), 0, 255).astype(np.uint8)
