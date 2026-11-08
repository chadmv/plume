"""Finishing the shade layout's B channel: easing thin pixels into their body's shade, then the divisor
that maps the brightest well-covered smoke of the run to 1.

A thin edge pixel's own shade is noisy (little smoke decides it) and an empty pixel has none, so a game
that filters or mipmaps the sheet would mix speckle or a dark outline into the smoke's edge. Easing gives
each thin pixel the thickness-weighted shade of its neighborhood, the body it belongs to.
"""

import numpy as np

from plume.render.raw_frame import SHADE, THICKNESS
from plume.sheet.soften import blur

# How much thickness the frame's mean shade counts as in every neighborhood: where the blurred smoke is
# well under one G step (1/255), the neighborhood's shade leans to the frame's mean rather than to a few
# faint pixels (bicubic ringing leaves such pixels with thickness but no shade).
FRAME_MEAN_WEIGHT = 1.0 / 255.0
# Thickness at or below this has no shade of its own.
NO_SMOKE = 1e-12


def ease_thin_pixels(frame: np.ndarray, fade_thickness: float, neighborhood_px: float) -> np.ndarray:
    """The frame with its SHADE slot turned from shade times thickness into shade (0 to 1), each pixel's
    eased toward its neighborhood's below `fade_thickness`.

    neighborhood = (blur(shade * thickness) + m * mean) / (blur(thickness) + m), Gaussian sigma
    `neighborhood_px`, where mean is the frame's thickness-weighted mean shade (0 in a frame with no smoke)
    and m is FRAME_MEAN_WEIGHT: where the blurred thickness is near zero, the frame's mean.
    shade = lerp(neighborhood, shade, clamp(thickness / fade_thickness, 0, 1)).
    """
    thickness = frame[..., THICKNESS]
    weighted_shade = frame[..., SHADE]
    total = float(thickness.sum())
    frame_mean = float(weighted_shade.sum()) / total if total > 0.0 else 0.0
    neighborhood = ((blur(weighted_shade, neighborhood_px) + FRAME_MEAN_WEIGHT * frame_mean)
                    / (blur(thickness, neighborhood_px) + FRAME_MEAN_WEIGHT))
    has_smoke = thickness > NO_SMOKE
    own = np.clip(np.where(has_smoke, weighted_shade / np.where(has_smoke, thickness, 1.0), 0.0), 0.0, 1.0)
    weight = np.clip(thickness / fade_thickness, 0.0, 1.0)
    result = frame.copy()
    result[..., SHADE] = neighborhood + weight * (own - neighborhood)
    return result


def shade_divisor(frames: list[np.ndarray], fade_thickness: float) -> float:
    """The largest shade of any pixel at least `fade_thickness` thick in the run.

    With no such pixel, the largest shade of any pixel with smoke; with no smoke at all, 1.
    """
    for floor in (fade_thickness, np.finfo(np.float64).tiny):
        shades = [frame[..., SHADE][frame[..., THICKNESS] >= floor] for frame in frames]
        largest = max((float(values.max()) for values in shades if values.size), default=0.0)
        if largest > 0.0:
            return largest
    return 1.0
