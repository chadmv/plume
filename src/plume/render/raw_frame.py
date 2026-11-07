"""The raw frame image: what the renderer keeps of each frame, a float image over the whole domain view.

Shape (height, width, 5): heat (glow integral, K m), thickness (0 to 1), and the camera-space normal.
"""

HEAT = 0
THICKNESS = 1
NORMAL_X = 2
NORMAL_Y = 3
NORMAL_Z = 4
CHANNELS = 5
