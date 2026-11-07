"""Assembling the sheet's frames from raw frame images, in the spec's order:
content, square crop, resample, soften, (shade layout) ease thin pixels and normalize shade, normalize
heat, quantize, and check the gutter (growing the margin and starting over from the crop when a frame's
content reaches its edge)."""

from dataclasses import dataclass

import numpy as np

from plume.recipe.schema import SHADE_LAYOUT, RenderSettings
from plume.render.camera import DomainView
from plume.render.raw_frame import HEAT
from plume.sheet.crop import CropSquare, content_box, square_crop
from plume.sheet.quantize import quantize
from plume.sheet.resample import resample_frame
from plume.sheet.shade import ease_thin_pixels, shade_divisor
from plume.sheet.soften import soften

GUTTER_PX = 2
MARGIN_GROWTH = 0.02
MAX_MARGIN_TRIES = 8


@dataclass(frozen=True)
class AssembledFrames:
    frames: list[np.ndarray]  # (frame_px, frame_px, 4) uint8 each
    crop: CropSquare
    margin: float
    frame_m: float
    seat: tuple[float, float]
    heat_divisor: float  # K m: the softened heat that maps to R = 255
    shade_divisor: float | None  # the eased shade that maps to B = 255; None in the normal layout


class GutterError(Exception):
    """Content still reaches a frame's edge after growing the margin the maximum number of times."""


def assemble(raw_frames: list[np.ndarray], view: DomainView, seat_world_m: np.ndarray, frame_px: int,
             render: RenderSettings, channels: str) -> AssembledFrames:
    """The quantized frames and the facts the JSON and reports need."""
    box = content_box(raw_frames)
    margin = render.crop_margin
    for _ in range(MAX_MARGIN_TRIES + 1):
        crop = square_crop(box, margin)
        finished = [soften(resample_frame(raw, crop, frame_px, channels), render.soften_px, channels)
                    for raw in raw_frames]
        divisor = None
        if channels == SHADE_LAYOUT:
            finished = [ease_thin_pixels(frame, render.shade_fade_thickness, render.shade_neighborhood_px)
                        for frame in finished]
            divisor = shade_divisor(finished, render.shade_fade_thickness)
        heat_divisor = max(float(frame[..., HEAT].max()) for frame in finished)
        frames = [quantize(frame, heat_divisor, channels, divisor or 1.0) for frame in finished]
        if all(_gutter_is_empty(frame) for frame in frames):
            return AssembledFrames(frames=frames, crop=crop, margin=margin, frame_m=crop.side * view.pixel_m,
                                   seat=_seat(view, crop, seat_world_m), heat_divisor=heat_divisor,
                                   shade_divisor=divisor)
        margin += MARGIN_GROWTH
    raise GutterError(f"content still touches the frame edge with crop_margin {margin:.2f}")


def _gutter_is_empty(frame: np.ndarray) -> bool:
    ring = np.ones(frame.shape[:2], dtype=bool)
    ring[GUTTER_PX:-GUTTER_PX, GUTTER_PX:-GUTTER_PX] = False
    return not np.any(frame[ring][:, :2])


def _seat(view: DomainView, crop: CropSquare, seat_world_m: np.ndarray) -> tuple[float, float]:
    x, y = view.to_pixels(seat_world_m)
    return (x - crop.left) / crop.side, (y - crop.top) / crop.side
