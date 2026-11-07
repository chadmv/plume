"""Resampling a frame's crop square to the sheet's frame size (bicubic, area-aware when shrinking)."""

import math

import numpy as np
from PIL import Image

from plume.render.raw_frame import CHANNELS, HEAT, NORMAL_Z, THICKNESS
from plume.sheet.crop import CropSquare

# Extra empty pixels around a padded frame, so bicubic taps never read past the padding.
PAD_SLACK_PX = 4


def resample_frame(raw: np.ndarray, crop: CropSquare, frame_px: int) -> np.ndarray:
    """The crop square of a raw frame as a (frame_px, frame_px, 5) float image."""
    padded, shift = _pad_to_cover(raw, crop)
    left, top, right, bottom = crop.box()
    box = (left + shift, top + shift, right + shift, bottom + shift)
    channels = []
    for channel in range(CHANNELS):
        image = Image.fromarray(np.ascontiguousarray(padded[..., channel], dtype=np.float32))
        channels.append(np.asarray(image.resize((frame_px, frame_px), Image.Resampling.BICUBIC, box=box)))
    frame = np.stack(channels, axis=-1).astype(np.float64)
    frame[..., THICKNESS] = np.clip(frame[..., THICKNESS], 0.0, 1.0)
    frame[..., HEAT] = np.maximum(frame[..., HEAT], 0.0)
    return frame


def _pad_to_cover(raw: np.ndarray, crop: CropSquare) -> tuple[np.ndarray, int]:
    """Pads with empty space (no heat or smoke, camera-facing normal) so the crop lies inside."""
    height, width = raw.shape[:2]
    left, top, right, bottom = crop.box()
    overflow = max(0.0, -left, -top, right - width, bottom - height)
    pad = math.ceil(overflow) + PAD_SLACK_PX
    padded = np.zeros((height + 2 * pad, width + 2 * pad, CHANNELS), dtype=np.float32)
    padded[..., NORMAL_Z] = 1.0
    padded[pad:pad + height, pad:pad + width] = raw
    return padded, pad
