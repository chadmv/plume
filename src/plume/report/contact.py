"""Contact sheets: every frame composited over a background, shrunk, numbered, in the sheet's grid."""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from plume.recipe.schema import LookSettings
from plume.report.color import to_srgb_bytes
from plume.report.composite import composite

GAP_PX = 2
GAP_COLOR = (40, 40, 40)
LABEL_COLOR = (255, 255, 255)
LABEL_SHADOW = (0, 0, 0)
LABEL_SIZE_PX = 11


def contact_sheet(frames: list[np.ndarray], columns: int, background_hex: str, look: LookSettings) -> Image.Image:
    """Each frame composited, shrunk to `look.contact_px`, numbered in its top-left corner."""
    size = look.contact_px
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * (size + GAP_PX) + GAP_PX, rows * (size + GAP_PX) + GAP_PX), GAP_COLOR)
    draw = ImageDraw.Draw(sheet)
    font = label_font()
    for index, frame in enumerate(frames):
        thumbnail = composited_image(frame, background_hex, look).resize((size, size), Image.Resampling.LANCZOS)
        row, column = divmod(index, columns)
        x = GAP_PX + column * (size + GAP_PX)
        y = GAP_PX + row * (size + GAP_PX)
        sheet.paste(thumbnail, (x, y))
        draw_label(draw, (x + 3, y + 2), str(index), font)
    return sheet


def composited_image(frame: np.ndarray, background_hex: str, look: LookSettings) -> Image.Image:
    """One frame over a background, as an sRGB image at the frame's own size."""
    return Image.fromarray(to_srgb_bytes(composite(frame, background_hex, look)))


def label_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=LABEL_SIZE_PX)


def draw_label(draw: ImageDraw.ImageDraw, position: tuple[int, int], text: str,
               font: ImageFont.ImageFont | ImageFont.FreeTypeFont) -> None:
    """White text with a one-pixel shadow, readable on any background."""
    x, y = position
    draw.text((x + 1, y + 1), text, fill=LABEL_SHADOW, font=font)
    draw.text((x, y), text, fill=LABEL_COLOR, font=font)
