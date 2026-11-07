"""Finding the crop: the square around everything any frame shows, plus a margin."""

from dataclasses import dataclass

import numpy as np

from plume.render.raw_frame import HEAT, THICKNESS

# A pixel is content when it would quantize to a byte of at least 1.
CONTENT_LEVEL = 0.5 / 255.0


@dataclass(frozen=True)
class CropSquare:
    """A square in domain-view pixel coordinates (continuous, may extend past the view)."""

    left: float
    top: float
    side: float

    def box(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.left + self.side, self.top + self.side)


class NothingVisibleError(Exception):
    """No frame shows any smoke or heat, so there is nothing to crop to."""


def content_box(raw_frames: list[np.ndarray]) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) pixel bounds, right and bottom exclusive, of content in any frame."""
    heat_max = max(float(frame[..., HEAT].max()) for frame in raw_frames)
    union = np.zeros(raw_frames[0].shape[:2], dtype=bool)
    for frame in raw_frames:
        union |= frame[..., THICKNESS] >= CONTENT_LEVEL
        if heat_max > 0.0:
            union |= frame[..., HEAT] >= CONTENT_LEVEL * heat_max
    rows = np.nonzero(union.any(axis=1))[0]
    columns = np.nonzero(union.any(axis=0))[0]
    if rows.size == 0:
        raise NothingVisibleError("no frame shows any smoke or heat; check the emitters and the camera")
    return int(columns[0]), int(rows[0]), int(columns[-1]) + 1, int(rows[-1]) + 1


def square_crop(box: tuple[int, int, int, int], margin: float) -> CropSquare:
    """The content box grown to a square around its center, then by `margin` of its side on each side."""
    left, top, right, bottom = box
    side = max(right - left, bottom - top) * (1.0 + 2.0 * margin)
    center_x = (left + right) / 2.0
    center_y = (top + bottom) / 2.0
    return CropSquare(left=center_x - side / 2.0, top=center_y - side / 2.0, side=side)
