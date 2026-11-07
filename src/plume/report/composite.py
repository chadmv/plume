"""The reference composite: how a sheet frame looks in game, the formula Petri's shader is to match.

    color = background * (1 - G) + G * smoke_ramp(heat) * light(normal) + emission_ramp(heat)

in linear light (premultiplied: the smoke layer covers the background, the glow adds on top), with
light(n) = ambient + (1 - ambient) * max(0, n . sun).
"""

from dataclasses import dataclass

import numpy as np

from plume.recipe.schema import LookSettings
from plume.report.color import hex_to_linear, ramp


@dataclass(frozen=True)
class DecodedFrame:
    heat: np.ndarray  # 0..1
    thickness: np.ndarray  # 0..1
    normal: np.ndarray  # (..., 3) unit vectors, camera space


def decode(rgba: np.ndarray) -> DecodedFrame:
    """Reads a sheet frame back the way Petri will: z is rebuilt from x and y."""
    values = rgba.astype(np.float64) / 255.0
    nx = values[..., 2] * 2.0 - 1.0
    ny = values[..., 3] * 2.0 - 1.0
    nz = np.sqrt(np.maximum(0.0, 1.0 - nx**2 - ny**2))
    return DecodedFrame(heat=values[..., 0], thickness=values[..., 1], normal=np.stack([nx, ny, nz], axis=-1))


def composite(rgba: np.ndarray, background_hex: str, look: LookSettings) -> np.ndarray:
    """The frame over a flat background, as linear RGB."""
    frame = decode(rgba)
    sun = np.array(look.sun_dir, dtype=np.float64)
    sun /= np.linalg.norm(sun)
    light = look.ambient + (1.0 - look.ambient) * np.maximum(0.0, frame.normal @ sun)
    thickness = frame.thickness[..., None]
    smoke = ramp(look.smoke_ramp, frame.heat) * light[..., None]
    glow = ramp(look.emission_ramp, frame.heat)
    return hex_to_linear(background_hex) * (1.0 - thickness) + thickness * smoke + glow
