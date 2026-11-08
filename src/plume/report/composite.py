"""The reference composite: how a sheet frame looks in game, the formula a game's shader is to match.

In linear light (premultiplied: the smoke layer covers the background, the glow adds on top):

    color = background * (1 - G) + G * smoke_ramp(heat) * light + emission_ramp(heat)

where light, by the sheet's channel layout, is
- shade layout: 1 - shade_depth * (1 - shade), the baked shade from B;
- normal layout: ambient + (1 - ambient) * max(0, n . light_dir), the normal from B and A.
"""

from dataclasses import dataclass

import numpy as np

from plume.recipe.schema import SHADE_LAYOUT, LookSettings, Recipe, Vec3
from plume.report.color import hex_to_linear, ramp


@dataclass(frozen=True)
class SheetLook:
    """What the reports need to light a sheet: the contact sheet look, the channel layout and the key
    light."""

    look: LookSettings
    channels: str
    light_dir: Vec3  # toward the key light, camera space


def sheet_look(recipe: Recipe) -> SheetLook:
    return SheetLook(look=recipe.look, channels=recipe.output.channels, light_dir=recipe.render.light_dir)


@dataclass(frozen=True)
class DecodedFrame:
    heat: np.ndarray  # 0..1
    thickness: np.ndarray  # 0..1
    shade: np.ndarray | None  # 0..1 in the shade layout, else None
    normal: np.ndarray | None  # (..., 3) unit vectors, camera space, in the normal layout, else None


def decode(rgba: np.ndarray, channels: str) -> DecodedFrame:
    """Reads a sheet frame back the way a game would; a normal's z is rebuilt from x and y."""
    values = rgba.astype(np.float64) / 255.0
    heat, thickness = values[..., 0], values[..., 1]
    if channels == SHADE_LAYOUT:
        return DecodedFrame(heat=heat, thickness=thickness, shade=values[..., 2], normal=None)
    nx = values[..., 2] * 2.0 - 1.0
    ny = values[..., 3] * 2.0 - 1.0
    nz = np.sqrt(np.maximum(0.0, 1.0 - nx**2 - ny**2))
    return DecodedFrame(heat=heat, thickness=thickness, shade=None, normal=np.stack([nx, ny, nz], axis=-1))


def composite(rgba: np.ndarray, background_hex: str, style: SheetLook) -> np.ndarray:
    """The frame over a flat background, as linear RGB."""
    look = style.look
    frame = decode(rgba, style.channels)
    if frame.shade is not None:
        light = 1.0 - look.shade_depth * (1.0 - frame.shade)
    else:
        toward_light = np.array(style.light_dir, dtype=np.float64)
        toward_light /= np.linalg.norm(toward_light)
        light = look.ambient + (1.0 - look.ambient) * np.maximum(0.0, frame.normal @ toward_light)
    thickness = frame.thickness[..., None]
    smoke = ramp(look.smoke_ramp, frame.heat) * light[..., None]
    glow = ramp(look.emission_ramp, frame.heat)
    return hex_to_linear(background_hex) * (1.0 - thickness) + thickness * smoke + glow
