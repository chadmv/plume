"""The frame cache: each kept frame's smoke and temperature, and its velocity at cell centers, as 16-bit
floats on the simulation's device.

A budget in bytes bounds the cache. Before a run, from the frame count and grid size, the cache plans what
it keeps (section 3.3): every frame with velocity when they fit; else every frame without velocity (the
slice plane then offers smoke and temperature only); else every second frame, then every fourth, and so on,
without velocity. Playback skips the frames that were not kept, never interpolating. Drawing a frame widens
it into 32-bit scratch arrays, since the ray march reads 32-bit fields; each reader (a viewport, a
re-capture) owns its scratch, since one cache can be read by the A and B views and a re-capture at once.

Velocity is kept at cell centers (the simulation's own centering, `sim/vorticity.py`), one 16-bit vector per
cell, since the slice plane reads speed and swirl at cell centers.
"""

import math

import warp as wp

from plume.sim.vorticity import center_velocity_kernel

SCALAR_FIELDS = 2  # smoke and temperature
VELOCITY_VALUES = 3  # one vector per cell
BYTES_PER_VALUE = 2  # float16


@wp.kernel
def narrow_kernel(source: wp.array3d(dtype=float), target: wp.array3d(dtype=wp.float16)):
    i, j, k = wp.tid()
    target[i, j, k] = wp.float16(source[i, j, k])


@wp.kernel
def widen_kernel(source: wp.array3d(dtype=wp.float16), target: wp.array3d(dtype=float)):
    i, j, k = wp.tid()
    target[i, j, k] = float(source[i, j, k])


@wp.kernel
def narrow_vector_kernel(source: wp.array3d(dtype=wp.vec3), target: wp.array3d(dtype=wp.vec3h)):
    i, j, k = wp.tid()
    value = source[i, j, k]
    target[i, j, k] = wp.vec3h(wp.float16(value[0]), wp.float16(value[1]), wp.float16(value[2]))


@wp.kernel
def widen_vector_kernel(source: wp.array3d(dtype=wp.vec3h), target: wp.array3d(dtype=wp.vec3)):
    i, j, k = wp.tid()
    value = source[i, j, k]
    target[i, j, k] = wp.vec3(float(value[0]), float(value[1]), float(value[2]))


def frame_bytes(cells: tuple[int, int, int], velocity: bool = False) -> int:
    """Bytes one kept frame takes, with or without its velocity."""
    values = SCALAR_FIELDS + (VELOCITY_VALUES if velocity else 0)
    return values * BYTES_PER_VALUE * math.prod(cells)


def frame_stride(frames: int, cells: tuple[int, int, int], budget_bytes: float) -> int:
    """The smallest power-of-two stride whose kept frames (0, stride, 2 * stride, ...) fit the budget without
    velocity; one frame is always kept."""
    stride = 1
    while stride < frames and math.ceil(frames / stride) * frame_bytes(cells) > budget_bytes:
        stride *= 2
    return stride


def keeps_velocity(frames: int, cells: tuple[int, int, int], budget_bytes: float) -> bool:
    """Whether every frame fits the budget with its velocity (velocity is the first thing dropped)."""
    return frames * frame_bytes(cells, velocity=True) <= budget_bytes


class FrameCache:
    """Kept frames of one run, filled in frame order as the run lands them."""

    def __init__(self, cells: tuple[int, int, int], frames: int, budget_bytes: float, device: str,
                 shared_with_compare: bool = False):
        self.cells = cells
        self.frames = frames
        self.budget_bytes = budget_bytes
        self.device = device
        self.shared_with_compare = shared_with_compare  # the budget is what the Compare run left
        self.has_velocity = keeps_velocity(frames, cells, budget_bytes)
        self.stride = 1 if self.has_velocity else frame_stride(frames, cells, budget_bytes)
        self._stored: dict[int, tuple[wp.array, wp.array]] = {}
        self._velocity: dict[int, wp.array] = {}
        self._centered: wp.array | None = None  # the store's scratch for centering a frame's velocity

    def keeps(self, frame: int) -> bool:
        """Whether this run keeps `frame` at its stride."""
        return frame % self.stride == 0

    def store(self, frame: int, smoke: wp.array, temperature: wp.array,
              velocity: tuple[wp.array, wp.array, wp.array] | None = None) -> None:
        """Rounds a kept frame's live fields to 16 bits and stores them; other frames are ignored. `velocity`
        is the grid's three face arrays (u, v, w), kept at cell centers when the plan keeps velocity."""
        if not self.keeps(frame):
            return
        stored = tuple(wp.empty(self.cells, dtype=wp.float16, device=self.device) for _ in range(SCALAR_FIELDS))
        for source, target in zip((smoke, temperature), stored, strict=True):
            wp.launch(narrow_kernel, dim=self.cells, device=self.device, inputs=[source, target])
        self._stored[frame] = stored
        if self.has_velocity and velocity is not None:
            if self._centered is None:
                self._centered = wp.empty(self.cells, dtype=wp.vec3, device=self.device)
            wp.launch(center_velocity_kernel, dim=self.cells, device=self.device, inputs=[*velocity, self._centered])
            kept = wp.empty(self.cells, dtype=wp.vec3h, device=self.device)
            wp.launch(narrow_vector_kernel, dim=self.cells, device=self.device, inputs=[self._centered, kept])
            self._velocity[frame] = kept

    def kept_frames(self) -> list[int]:
        """The frames stored so far, in order."""
        return sorted(self._stored)

    def nearest_kept(self, frame: int) -> int | None:
        """The latest stored frame at or before `frame`, or the first stored frame; None when empty."""
        kept = self.kept_frames()
        if not kept:
            return None
        earlier = [index for index in kept if index <= frame]
        return earlier[-1] if earlier else kept[0]

    @property
    def stored_bytes(self) -> int:
        """Device bytes the kept frames take."""
        return (len(self._stored) * frame_bytes(self.cells)
                + len(self._velocity) * (frame_bytes(self.cells, velocity=True) - frame_bytes(self.cells)))

    @property
    def thinned(self) -> bool:
        """Whether the budget made the cache skip frames."""
        return self.stride > 1

    def scratch(self) -> tuple[wp.array, wp.array]:
        """A 32-bit smoke and temperature pair for one reader's loads."""
        return (wp.zeros(self.cells, dtype=float, device=self.device),
                wp.zeros(self.cells, dtype=float, device=self.device))

    def velocity_scratch(self) -> wp.array:
        """A 32-bit center velocity array for one reader's `load_velocity`."""
        return wp.zeros(self.cells, dtype=wp.vec3, device=self.device)

    def load(self, frame: int, into: tuple[wp.array, wp.array]) -> tuple[wp.array, wp.array]:
        """A stored frame's smoke and temperature widened to 32 bits into the reader's `into` pair (from
        `scratch`), which the reader's next load overwrites."""
        for source, target in zip(self._stored[frame], into, strict=True):
            wp.launch(widen_kernel, dim=self.cells, device=self.device, inputs=[source, target])
        return into

    def velocity_kept(self, frame: int) -> bool:
        """Whether `frame` was stored with its velocity."""
        return frame in self._velocity

    def load_velocity(self, frame: int, into: wp.array) -> wp.array:
        """A stored frame's center velocity (m/s) widened to 32 bits into the reader's `into` (from
        `velocity_scratch`). The frame must have one (`velocity_kept`)."""
        wp.launch(widen_vector_kernel, dim=self.cells, device=self.device, inputs=[self._velocity[frame], into])
        return into

    def stored_smoke(self, frame: int) -> wp.array:
        """The 16-bit smoke as stored, for tests and host-side reads."""
        return self._stored[frame][0]

    def stored_velocity(self, frame: int) -> wp.array:
        """The 16-bit center velocity as stored, for tests."""
        return self._velocity[frame]

    def thinning_note(self) -> str | None:
        """A status line when the budget made the cache drop velocity or skip frames, else None."""
        if self.has_velocity:
            return None
        gigabytes = self.budget_bytes / 2**30
        room = ("the room the Compare run leaves of --cache-gb" if self.shared_with_compare else "--cache-gb")
        if self.stride == 1:
            return (f"frame cache keeps no velocity (the slice plane offers smoke and temperature only): "
                    f"{self.frames} frames at {frame_bytes(self.cells, velocity=True) / 2**20:.1f} MB each with "
                    f"velocity do not fit {gigabytes:.3g} GB ({room})")
        return (f"frame cache keeps every {_ordinal(self.stride)} frame and no velocity: {self.frames} frames at "
                f"{frame_bytes(self.cells) / 2**20:.1f} MB each do not fit {gigabytes:.3g} GB ({room})")


def _ordinal(number: int) -> str:
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10 if number % 100 not in (11, 12, 13) else 0, "th")
    return f"{number}{suffix}"
