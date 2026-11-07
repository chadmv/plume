"""Packing frames into the sheet image (rows left to right, top to bottom) and writing PNGs."""

import math
from pathlib import Path

import numpy as np
from PIL import Image

PNG_COMPRESS_LEVEL = 6


def pack(frames: list[np.ndarray], columns: int) -> np.ndarray:
    """One image holding every frame; slots past the last frame are all zero."""
    size = frames[0].shape[0]
    rows = math.ceil(len(frames) / columns)
    sheet = np.zeros((rows * size, columns * size, frames[0].shape[2]), dtype=frames[0].dtype)
    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        sheet[row * size:(row + 1) * size, column * size:(column + 1) * size] = frame
    return sheet


def write_png(path: Path, image: np.ndarray) -> None:
    """Writes an 8-bit image with fixed settings and no metadata, so equal pixels give equal bytes."""
    Image.fromarray(image).save(path, format="PNG", compress_level=PNG_COMPRESS_LEVEL)
