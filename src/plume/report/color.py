"""Color helpers for the reports: sRGB conversion and color ramps interpolated in linear light."""

import numpy as np

from plume.recipe.schema import ColorStop


def srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    """sRGB 0..1 to linear 0..1 (the standard piecewise curve)."""
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    """Linear 0..1 to sRGB 0..1, clamping first."""
    linear = np.clip(linear, 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1.0 / 2.4) - 0.055)


def hex_to_linear(color: str) -> np.ndarray:
    """A "#rrggbb" sRGB color as a linear RGB triple."""
    srgb = np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64) / 255.0
    return srgb_to_linear(srgb)


def to_srgb_bytes(linear: np.ndarray) -> np.ndarray:
    """A linear image as 8-bit sRGB."""
    return np.floor(linear_to_srgb(linear) * 255.0 + 0.5).astype(np.uint8)


def ramp(stops: tuple[ColorStop, ...], values: np.ndarray) -> np.ndarray:
    """Linear RGB for each value (0..1) along the ramp; values past the ends take the end colors."""
    positions = np.array([position for position, _ in stops])
    colors = np.array([hex_to_linear(color) for _, color in stops])
    return np.stack([np.interp(values, positions, colors[:, channel]) for channel in range(3)], axis=-1)
