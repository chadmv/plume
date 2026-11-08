"""The channel strip: six evenly spaced frames at full size, each channel shown on its own.

Columns: heat as gray, thickness as gray, then by layout the shade as gray or the normal as color
((n + 1) / 2 as RGB, z rebuilt), and the composite over the neutral background.
"""

import numpy as np
from PIL import Image, ImageDraw

from plume.recipe.schema import SHADE_LAYOUT
from plume.report.composite import SheetLook, decode
from plume.report.contact import GAP_COLOR, GAP_PX, composited_image, draw_label, label_font

STRIP_FRAMES = 6
COLUMN_COUNT = 4
HEADER_PX = 18


def strip_frame_indices(frame_count: int) -> list[int]:
    """Up to six frame indices evenly spaced from the first to the last."""
    count = min(STRIP_FRAMES, frame_count)
    if count == 1:
        return [0]
    return sorted({round(i * (frame_count - 1) / (count - 1)) for i in range(count)})


def channel_strip(frames: list[np.ndarray], style: SheetLook) -> Image.Image:
    """The strip image for the run's frames."""
    size = frames[0].shape[0]
    indices = strip_frame_indices(len(frames))
    width = COLUMN_COUNT * (size + GAP_PX) + GAP_PX
    height = HEADER_PX + len(indices) * (size + GAP_PX) + GAP_PX
    strip = Image.new("RGB", (width, height), GAP_COLOR)
    draw = ImageDraw.Draw(strip)
    font = label_font()
    for column, title in enumerate(_titles(style.channels)):
        draw_label(draw, (GAP_PX + column * (size + GAP_PX) + 3, 3), title, font)
    for row, index in enumerate(indices):
        y = HEADER_PX + row * (size + GAP_PX)
        for column, panel in enumerate(_panels(frames[index], style)):
            strip.paste(panel, (GAP_PX + column * (size + GAP_PX), y))
        draw_label(draw, (GAP_PX + 3, y + 2), f"frame {index}", font)
    return strip


def _titles(channels: str) -> tuple[str, ...]:
    return ("heat", "thickness", "shade" if channels == SHADE_LAYOUT else "normal", "composite")


def _panels(frame: np.ndarray, style: SheetLook) -> list[Image.Image]:
    if style.channels == SHADE_LAYOUT:
        third = Image.fromarray(frame[..., 2]).convert("RGB")
    else:
        normal = decode(frame, style.channels).normal
        third = Image.fromarray(np.floor((normal + 1.0) * 0.5 * 255.0 + 0.5).astype(np.uint8))
    return [
        Image.fromarray(frame[..., 0]).convert("RGB"),
        Image.fromarray(frame[..., 1]).convert("RGB"),
        third,
        composited_image(frame, style.look.backgrounds.neutral, style),
    ]
