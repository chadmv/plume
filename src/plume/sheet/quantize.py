"""Quantizing a finished float frame into the sheet's four 8-bit channels, by channel layout.

R = heat / heat divisor, G = thickness, both layouts. Then:
- shade layout: B = shade / shade divisor, A = 255 (unused).
- normal layout: B and A = camera-space normal x and y mapped from -1..1 to 0..255 (so a camera-facing
  normal reads 128, 128 and A = 255 faces up); where a pixel is empty (R and G both 0), B and A are
  exactly 128.
All linear; values round half up.
"""

import numpy as np

from plume.recipe.schema import SHADE_LAYOUT
from plume.render.raw_frame import HEAT, NORMAL_X, NORMAL_Y, SHADE, THICKNESS

FACING_BYTE = 128
UNUSED_BYTE = 255


def quantize(frame: np.ndarray, heat_divisor: float, channels: str, shade_divisor: float = 1.0) -> np.ndarray:
    """A (size, size, 4) uint8 RGBA frame from a (size, size, 5) float frame."""
    heat = frame[..., HEAT] / heat_divisor if heat_divisor > 0.0 else np.zeros(frame.shape[:2])
    red_green = [_to_byte(heat), _to_byte(frame[..., THICKNESS])]
    if channels == SHADE_LAYOUT:
        return np.stack([*red_green, _to_byte(frame[..., SHADE] / shade_divisor),
                         np.full(frame.shape[:2], UNUSED_BYTE, dtype=np.uint8)], axis=-1)
    rgba = np.stack([
        *red_green,
        _to_byte((frame[..., NORMAL_X] + 1.0) * 0.5),
        _to_byte((frame[..., NORMAL_Y] + 1.0) * 0.5),
    ], axis=-1)
    empty = (rgba[..., 0] == 0) & (rgba[..., 1] == 0)
    rgba[empty, 2] = FACING_BYTE
    rgba[empty, 3] = FACING_BYTE
    return rgba


def _to_byte(values: np.ndarray) -> np.ndarray:
    return np.clip(np.floor(values * 255.0 + 0.5), 0, 255).astype(np.uint8)
