"""Guides over the Volume view (G): the domain box, 0.5 m ticks along the floor's edges, each emitter's
outline and the key light's direction, as world-space segments projected to the screen.

The box: an edge is solid when either face it borders is closed and dashed when both are open, so a closed
floor under open walls reads as a solid floor outline with dashed walls. An emitter's outline is dashed
for a frame whose block of steps it was off for the whole of.
"""

import math
from dataclasses import dataclass

import numpy as np

from plume.recipe.derived import Derived
from plume.recipe.schema import EmitterSettings, FaceSettings, Recipe
from plume.view.navigation import ViewCamera

TICK_SPACING_M = 0.5
TICK_LENGTH_SHARE = 0.02  # of the larger floor side
CIRCLE_SEGMENTS = 48
ARROW_LENGTH_SHARE = 0.35  # of the domain's largest side
ARROW_HEAD_SHARE = 0.2  # of the arrow's length
NEAR_M = 0.01  # perspective segments are clipped this far in front of the eye
DASH_PX = 7.0
GAP_PX = 5.0

BOX, TICK, EMITTER, LIGHT = "box", "tick", "emitter", "light"


@dataclass(frozen=True)
class Segment:
    start: np.ndarray
    end: np.ndarray
    dashed: bool
    kind: str


def guide_segments(recipe: Recipe, derived: Derived, frame: int, toward_light_world: np.ndarray) -> list[Segment]:
    """Every guide segment for a frame of the run."""
    low = np.array(derived.domain_min_m, dtype=np.float64)
    size = np.array(derived.size_m, dtype=np.float64)
    end_s = derived.warmup_steps * derived.dt_s + derived.frame_time_s(frame)
    start_s = end_s - derived.steps_per_frame * derived.dt_s
    segments = box_edges(low, size, recipe.domain.faces) + floor_ticks(low, size)
    for emitter in recipe.emitter:
        segments += emitter_outline(emitter, start_s, end_s)
    return segments + light_arrow(low + size / 2, toward_light_world, ARROW_LENGTH_SHARE * float(size.max()))


def box_edges(low: np.ndarray, size: np.ndarray, faces: FaceSettings) -> list[Segment]:
    """The domain box's twelve edges with the dash rule above."""
    face_names = {(0, 0): faces.left, (0, 1): faces.right, (1, 0): faces.bottom, (1, 1): faces.top,
                  (2, 0): faces.back, (2, 1): faces.front}
    segments = []
    for axis in range(3):
        others = [other for other in range(3) if other != axis]
        for side_a in (0, 1):
            for side_b in (0, 1):
                corner = low.copy()
                corner[others[0]] += side_a * size[others[0]]
                corner[others[1]] += side_b * size[others[1]]
                end = corner.copy()
                end[axis] += size[axis]
                both_open = face_names[(others[0], side_a)] == "open" and face_names[(others[1], side_b)] == "open"
                segments.append(Segment(corner, end, both_open, BOX))
    return segments


def floor_ticks(low: np.ndarray, size: np.ndarray) -> list[Segment]:
    """Ticks at every multiple of 0.5 m along the floor's four edges, pointing into the floor."""
    length = TICK_LENGTH_SHARE * max(size[0], size[2])
    segments = []
    for along, across in ((0, 2), (2, 0)):
        first = math.ceil(low[along] / TICK_SPACING_M - 1e-9)
        last = math.floor((low[along] + size[along]) / TICK_SPACING_M + 1e-9)
        for index in range(first, last + 1):
            for side, inward in ((low[across], 1.0), (low[across] + size[across], -1.0)):
                start = np.array([0.0, low[1], 0.0])
                start[along] = index * TICK_SPACING_M
                start[across] = side
                end = start.copy()
                end[across] += inward * length
                segments.append(Segment(start, end, False, TICK))
    return segments


def emitter_outline(emitter: EmitterSettings, block_start_s: float, block_end_s: float) -> list[Segment]:
    """A sphere as three circles, a box as its edges; dashed when the emitter was off for the whole block
    (it runs from `start_s` up to `end_s`)."""
    off = not (emitter.start_s < block_end_s and emitter.end_s > block_start_s)
    center = np.array(emitter.center_m, dtype=np.float64)
    if emitter.shape == "box":
        size = np.array(emitter.size_m, dtype=np.float64)
        return [Segment(edge.start, edge.end, off, EMITTER)
                for edge in box_edges(center - size / 2, size, FaceSettings())]
    segments = []
    angles = np.linspace(0.0, 2.0 * math.pi, CIRCLE_SEGMENTS + 1)
    for first, second in ((0, 1), (1, 2), (0, 2)):
        points = np.zeros((len(angles), 3))
        points[:, first] = np.cos(angles) * emitter.radius_m
        points[:, second] = np.sin(angles) * emitter.radius_m
        points += center
        segments += [Segment(points[i], points[i + 1], off, EMITTER) for i in range(CIRCLE_SEGMENTS)]
    return segments


def light_arrow(origin: np.ndarray, toward_light: np.ndarray, length: float) -> list[Segment]:
    """An arrow from `origin` toward the key light, with a two-line head."""
    direction = np.asarray(toward_light, dtype=np.float64)
    direction = direction / np.linalg.norm(direction)
    tip = origin + direction * length
    side = np.cross(direction, [0.0, 1.0, 0.0])
    if np.linalg.norm(side) < 1e-6:
        side = np.cross(direction, [1.0, 0.0, 0.0])
    side /= np.linalg.norm(side)
    head = length * ARROW_HEAD_SHARE
    back = tip - direction * head
    return [Segment(origin, tip, False, LIGHT), Segment(tip, back + side * head * 0.5, False, LIGHT),
            Segment(tip, back - side * head * 0.5, False, LIGHT)]


def on_screen(camera: ViewCamera, segment: Segment) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """The segment's pixel endpoints, clipped to just in front of a perspective eye; None when it is wholly
    behind."""
    start, end = segment.start, segment.end
    if camera.perspective:
        ahead_start, ahead_end = camera.ahead(start), camera.ahead(end)
        if ahead_start < NEAR_M and ahead_end < NEAR_M:
            return None
        if ahead_start < NEAR_M:
            start = start + (end - start) * (NEAR_M - ahead_start) / (ahead_end - ahead_start)
        elif ahead_end < NEAR_M:
            end = end + (start - end) * (NEAR_M - ahead_end) / (ahead_start - ahead_end)
    return camera.project(start), camera.project(end)


def dashes(start: tuple[float, float], end: tuple[float, float]) -> list[tuple[tuple[float, float],
                                                                             tuple[float, float]]]:
    """A screen segment split into dashes of DASH_PX with gaps of GAP_PX."""
    length = math.dist(start, end)
    if length == 0.0:
        return []
    pieces = []
    position = 0.0
    while position < length:
        stop = min(position + DASH_PX, length)
        pieces.append((_along(start, end, position / length), _along(start, end, stop / length)))
        position = stop + GAP_PX
    return pieces


def _along(start: tuple[float, float], end: tuple[float, float], share: float) -> tuple[float, float]:
    return start[0] + (end[0] - start[0]) * share, start[1] + (end[1] - start[1]) * share
