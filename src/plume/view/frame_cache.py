"""The frame cache: each kept frame's smoke and temperature, as 16-bit floats on the simulation's device.

A budget in bytes bounds the cache. The stride is chosen before a run from the frame count and grid size:
every frame when they fit, else every second, then every fourth frame, and so on; playback skips the
frames that were not kept, never interpolating. Drawing a frame widens it into 32-bit scratch arrays,
since the ray march reads 32-bit fields; each reader (a viewport, a re-capture) owns its pair, since one
cache can be read by the A and B views and a re-capture at once.
"""

import math

import warp as wp

FIELDS = 2  # smoke and temperature
BYTES_PER_VALUE = 2  # float16


@wp.kernel
def narrow_kernel(source: wp.array3d(dtype=float), target: wp.array3d(dtype=wp.float16)):
    i, j, k = wp.tid()
    target[i, j, k] = wp.float16(source[i, j, k])


@wp.kernel
def widen_kernel(source: wp.array3d(dtype=wp.float16), target: wp.array3d(dtype=float)):
    i, j, k = wp.tid()
    target[i, j, k] = float(source[i, j, k])


def frame_bytes(cells: tuple[int, int, int]) -> int:
    """Bytes one kept frame takes."""
    return FIELDS * BYTES_PER_VALUE * math.prod(cells)


def frame_stride(frames: int, cells: tuple[int, int, int], budget_bytes: float) -> int:
    """The smallest power-of-two stride whose kept frames (0, stride, 2 * stride, ...) fit the budget; one
    frame is always kept."""
    stride = 1
    while stride < frames and math.ceil(frames / stride) * frame_bytes(cells) > budget_bytes:
        stride *= 2
    return stride


class FrameCache:
    """Kept frames of one run, filled in frame order as the run lands them."""

    def __init__(self, cells: tuple[int, int, int], frames: int, budget_bytes: float, device: str,
                 shared_with_compare: bool = False):
        self.cells = cells
        self.frames = frames
        self.budget_bytes = budget_bytes
        self.device = device
        self.shared_with_compare = shared_with_compare  # the budget is what the Compare run left
        self.stride = frame_stride(frames, cells, budget_bytes)
        self._stored: dict[int, tuple[wp.array, wp.array]] = {}

    def keeps(self, frame: int) -> bool:
        """Whether this run keeps `frame` at its stride."""
        return frame % self.stride == 0

    def store(self, frame: int, smoke: wp.array, temperature: wp.array) -> None:
        """Rounds a kept frame's live fields to 16 bits and stores them; other frames are ignored."""
        if not self.keeps(frame):
            return
        stored = tuple(wp.empty(self.cells, dtype=wp.float16, device=self.device) for _ in range(FIELDS))
        for source, target in zip((smoke, temperature), stored, strict=True):
            wp.launch(narrow_kernel, dim=self.cells, device=self.device, inputs=[source, target])
        self._stored[frame] = stored

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
        return len(self._stored) * frame_bytes(self.cells)

    @property
    def thinned(self) -> bool:
        """Whether the budget made the cache skip frames."""
        return self.stride > 1

    def scratch(self) -> tuple[wp.array, wp.array]:
        """A 32-bit smoke and temperature pair for one reader's loads."""
        return (wp.zeros(self.cells, dtype=float, device=self.device),
                wp.zeros(self.cells, dtype=float, device=self.device))

    def load(self, frame: int, into: tuple[wp.array, wp.array]) -> tuple[wp.array, wp.array]:
        """A stored frame's smoke and temperature widened to 32 bits into the reader's `into` pair (from
        `scratch`), which the reader's next load overwrites."""
        for source, target in zip(self._stored[frame], into, strict=True):
            wp.launch(widen_kernel, dim=self.cells, device=self.device, inputs=[source, target])
        return into

    def stored_smoke(self, frame: int) -> wp.array:
        """The 16-bit smoke as stored, for tests and host-side reads."""
        return self._stored[frame][0]

    def thinning_note(self) -> str | None:
        """A status line when the budget made the cache skip frames, else None."""
        if self.stride == 1:
            return None
        gigabytes = self.budget_bytes / 2**30
        room = ("the room the Compare run leaves of --cache-gb" if self.shared_with_compare else "--cache-gb")
        return (f"frame cache keeps every {_ordinal(self.stride)} frame: {self.frames} frames at "
                f"{frame_bytes(self.cells) / 2**20:.1f} MB each do not fit {gigabytes:.3g} GB ({room})")


def _ordinal(number: int) -> str:
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10 if number % 100 not in (11, 12, 13) else 0, "th")
    return f"{number}{suffix}"
