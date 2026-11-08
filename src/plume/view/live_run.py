"""A live run: the recipe's simulation advanced one frame at a time, so the window stays responsive.

Each frame is captured exactly as `plume run` captures it (the sheet camera's raw frame, through the same
`FrameRenderer`), and its smoke and temperature go into the frame cache for drawing from any angle. When
the last frame lands, the sheet is assembled on a worker thread (host numpy only; every Warp launch stays
on the window's thread) to give the sheet's heat and shade divisors and its crop.
"""

import itertools
import time
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np

from plume.recipe.derived import Derived
from plume.recipe.schema import Recipe
from plume.render.camera import sheet_domain_view
from plume.render.frame_renderer import FrameRenderer
from plume.render.raw_frame import HEAT
from plume.sheet.assemble import AssembledFrames, assemble, seat_point
from plume.sim.grid import GridInfo
from plume.sim.run import StepLog, simulate_frames
from plume.view.frame_cache import FrameCache


_SERIALS = itertools.count(1)


class LiveRun:
    """One run of a resolved recipe. Call `advance` once per window update until `done` or `stopped`."""

    def __init__(self, recipe: Recipe, derived: Derived, device: str, budget_bytes: float):
        self.serial = next(_SERIALS)  # tells runs apart; an id() could be reused once a run is freed
        self.recipe = recipe
        self.derived = derived
        self.device = device
        self.view = sheet_domain_view(recipe, derived)
        self.renderer = FrameRenderer(self.view, recipe.render, derived.cells, recipe.output.channels, device)
        self.cache = FrameCache(derived.cells, recipe.time.frames, budget_bytes, device)
        self.raw_frames: list[np.ndarray] = []
        self.info: GridInfo | None = None  # the grid's geometry, from the first frame
        self.steps: StepLog | None = None
        self.assembled: AssembledFrames | None = None
        self.assembly_error: str | None = None
        self.elapsed_s = 0.0
        self.started_s = time.perf_counter()
        self.stopped = False  # cancelled part way (a recipe error, or a newer run replaced it)
        self._frames = simulate_frames(recipe, derived, device)
        self._largest_raw_heat = 0.0
        self._assembly: Future | None = None
        self._executor: ThreadPoolExecutor | None = None

    @property
    def frames(self) -> int:
        return self.recipe.time.frames

    @property
    def landed(self) -> int:
        """Frames simulated so far."""
        return len(self.raw_frames)

    @property
    def done(self) -> bool:
        return self.steps is not None

    def advance(self) -> int | None:
        """Simulates and captures the next frame and returns its index; None once the run is done or
        stopped."""
        if self.done or self.stopped:
            return None
        frame, grid = next(self._frames)
        if self.info is None:
            self.info = grid.info
        raw = self.renderer.render(grid)
        self.raw_frames.append(raw)
        self._largest_raw_heat = max(self._largest_raw_heat, float(raw[..., HEAT].max()))
        self.cache.store(frame, grid.smoke.data, grid.temperature.data)
        if frame == self.frames - 1:
            self._finish()
        return frame

    def cancel(self) -> None:
        """Stops the run where it is; its frames stay drawable."""
        if not self.done and not self.stopped:
            self.stopped = True
            self.elapsed_s = time.perf_counter() - self.started_s
        self._frames.close()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def poll_assembly(self) -> bool:
        """Takes the sheet assembly's result once it is ready; True on the call that takes it."""
        if self._assembly is None or not self._assembly.done():
            return False
        future, self._assembly = self._assembly, None
        self._executor.shutdown(wait=False)
        try:
            self.assembled = future.result()
        except Exception as error:  # noqa: BLE001 - shown in the status line; the run stays drawable
            self.assembly_error = f"sheet assembly failed: {error}"
        return True

    def wait_for_assembly(self) -> None:
        """Blocks until the assembly has finished (for tests and scripts)."""
        if self._assembly is not None:
            self._assembly.exception()
            self.poll_assembly()

    @property
    def heat_divisor(self) -> float:
        """What heat 1 means: the sheet's divisor once assembled, else the largest raw heat so far."""
        divisor = self.assembled.heat_divisor if self.assembled else self._largest_raw_heat
        return divisor if divisor > 0.0 else 1.0

    @property
    def shade_divisor(self) -> float:
        """The sheet's shade divisor once assembled, else 1."""
        if self.assembled is None or self.assembled.shade_divisor is None:
            return 1.0
        return self.assembled.shade_divisor

    def _finish(self) -> None:
        try:
            next(self._frames)
        except StopIteration as finished:
            self.steps = finished.value
        self.elapsed_s = time.perf_counter() - self.started_s
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="plume-assemble")
        self._assembly = self._executor.submit(
            assemble, list(self.raw_frames), self.view, seat_point(self.recipe), self.recipe.output.frame_px,
            self.recipe.render, self.recipe.output.channels)
