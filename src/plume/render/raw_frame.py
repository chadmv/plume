"""The raw frame image: what the renderer keeps of each frame, a float image over the whole domain view.

Shape (height, width, 5): heat (glow integral, K m), thickness (0 to 1), then three channels whose meaning
follows the sheet's layout: the camera-space normal x, y and z in the normal layout, or the shade times
thickness and two zeros in the shade layout. Shade (0 to 1) is the opacity-weighted share of key light
reaching the smoke the camera sees; it is kept multiplied by thickness so that resampling and softening
weigh each pixel's shade by how much smoke it has, as they do the thickness itself (sheet/shade.py divides
it back out).
"""

import numpy as np

from plume.recipe.schema import NORMAL_LAYOUT

HEAT = 0
THICKNESS = 1
NORMAL_X = 2
NORMAL_Y = 3
NORMAL_Z = 4
SHADE = 2  # shade times thickness: the shade layout's use of the slot the normal layout gives NORMAL_X
CHANNELS = 5


def empty_pixel(channels: str) -> np.ndarray:
    """The raw value of empty space: nothing, and in the normal layout a normal that faces the camera."""
    pixel = np.zeros(CHANNELS, dtype=np.float32)
    if channels == NORMAL_LAYOUT:
        pixel[NORMAL_Z] = 1.0
    return pixel
