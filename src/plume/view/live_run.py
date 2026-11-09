"""A live run: the recipe's simulation advanced one frame at a time, so the window stays responsive.

Each frame is captured exactly as `plume run` captures it (the sheet camera's raw frame, through the same
`FrameRenderer`), and its smoke and temperature go into the frame cache for drawing from any angle. When
the last frame lands, the sheet is assembled on a worker thread (host numpy only; every Warp launch stays
on the window's thread) to give the sheet's heat and shade divisors and its crop.

A re-capture (a render or sheet edit, V11) is a run that shares a finished run's frame cache and, instead of
simulating, renders each kept frame's sheet-camera raw frame again with the new settings, one frame per
window update, then assembles. It reads the 16-bit kept fields, so its divisors can differ from `plume
run`'s in the last digits; until its assembly lands it reports the source run's divisors.

As each frame lands the run also notes which faces its smoke reached, for the numbers strip's marks: an
open face, or the ceiling whatever its kind, counts when any cell in the layer beside it holds at least the
density at which one cell shows one byte step (`visible_density`).
"""

import itertools
import math
import time
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np
import warp as wp

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
FACE_NAMES = ("left", "right", "bottom", "top", "back", "front")  # x low, x high, y low, y high, z low, z high
CEILING = "top"


@wp.kernel
def boundary_layer_kernel(smoke: wp.array3d(dtype=float), layers: wp.array3d(dtype=float)):
    """Copies the six boundary layers of the smoke into `layers[face, a, b]` (face in FACE_NAMES order; a and
    b the face's two other axes in x, y, z order); entries past a face's size are 0."""
    face, a, b = wp.tid()
    axis = face // 2
    first = wp.min((axis + 1) % 3, (axis + 2) % 3)
    second = wp.max((axis + 1) % 3, (axis + 2) % 3)
    if a >= smoke.shape[first] or b >= smoke.shape[second]:
        layers[face, a, b] = 0.0
        return
    cell = wp.vec3i(0, 0, 0)
    cell[axis] = (face % 2) * (smoke.shape[axis] - 1)
    cell[first] = a
    cell[second] = b
    layers[face, a, b] = smoke[cell[0], cell[1], cell[2]]


def visible_density(recipe: Recipe) -> float:
    """Smoke density at which one cell's opacity reaches one byte step (1/255)."""
    return -math.log(1.0 - 1.0 / 255.0) / (recipe.render.opacity_per_density * recipe.domain.cell_m)


def faces_reached(layers: np.ndarray, recipe: Recipe) -> tuple[str, ...]:
    """The open faces, and the ceiling, whose boundary layer (from `boundary_layer_kernel`) holds visible
    smoke, in FACE_NAMES order."""
    largest = layers.reshape(len(FACE_NAMES), -1).max(axis=1)
    threshold = visible_density(recipe)
    faces = recipe.domain.faces
    return tuple(name for name, value in zip(FACE_NAMES, largest, strict=True)
                 if value >= threshold and (name == CEILING or getattr(faces, name) == "open"))


class LiveRun:
    """One run of a resolved recipe. Call `advance` once per window update while it is `capturing`."""

    def __init__(self, recipe: Recipe, derived: Derived, device: str, budget_bytes: float,
                 shared_with_compare: bool = False, source: "LiveRun | None" = None):
        """A new run of `recipe`, or with `source`, a re-capture of a finished run's kept frames (use
        `recapture`)."""
        self.serial = next(_SERIALS)  # tells runs apart; an id() could be reused once a run is freed
        self.recipe = recipe
        self.derived = derived
        self.device = device
        self.view = sheet_domain_view(recipe, derived)
        self.renderer = FrameRenderer(self.view, recipe.render, derived.cells, recipe.output.channels, device)
        self.recaptured = source is not None
        self.source = source  # a re-capture's source, for its divisors until its own assembly lands
        self.raw_frames: list[np.ndarray] = []
        self.assembled: AssembledFrames | None = None
        self.assembly_error: str | None = None
        self.started_s = time.perf_counter()
        self.stopped = False  # cancelled part way (a recipe error, or a newer run replaced it)
        self._largest_raw_heat = 0.0
        self._layers: wp.array | None = None
        self._assembly: Future | None = None
        self._executor: ThreadPoolExecutor | None = None
        if source is None:
            self.simulation_serial = self.serial  # the simulation whose frames this run shows
            self.cache = FrameCache(derived.cells, recipe.time.frames, budget_bytes, device, shared_with_compare)
            self.info: GridInfo | None = None  # the grid's geometry, from the first frame
            self.steps: StepLog | None = None
            self.elapsed_s = 0.0
            self.edges: dict[int, tuple[str, ...]] = {}  # the faces each landed frame's smoke reached
            self._frames = simulate_frames(recipe, derived, device)
        else:
            self.simulation_serial = source.simulation_serial
            self.cache = source.cache
            self.info = source.info
            self.steps = source.steps
            self.elapsed_s = source.elapsed_s  # the simulation's time; a re-capture adds no simulation
            self.edges = source.edges
            self._frames = self._recaptured_frames()

    @classmethod
    def recapture(cls, source: "LiveRun", recipe: Recipe) -> "LiveRun":
        """A run of `recipe`, whose simulation stage equals the source's, over a finished source run's kept
        frames. The source must be able to (`can_recapture`)."""
        if not source.can_recapture():
            raise ValueError("a re-capture needs a finished run that kept every frame")
        if source.recaptured and source.capturing and source.source is not None:
            source = source.source  # a re-capture replaced part way: take the divisors of the run it came from
        return cls(recipe, source.derived, source.device, 0.0, source=source)

    def can_recapture(self) -> bool:
        """Whether a render or sheet edit can re-capture this run instead of re-running it: it finished and
        its cache kept every frame."""
        return self.done and not self.cache.thinned

    @property
    def capturing(self) -> bool:
        """Whether sheet-camera frames are still to come (simulating, or re-capturing)."""
        return not self.stopped and self.landed < self.frames

    @property
    def frames(self) -> int:
        return self.recipe.time.frames

    @property
    def landed(self) -> int:
        """Sheet-camera frames captured so far."""
        return len(self.raw_frames)

    @property
    def done(self) -> bool:
        return self.steps is not None

    def advance(self) -> int | None:
        """Simulates (or re-captures) and captures the next frame and returns its index; None once every
        frame is captured or the run stopped."""
        if not self.capturing:
            return None
        if self.recaptured:
            return next(self._frames)
        frame, grid = next(self._frames)
        if self.info is None:
            self.info = grid.info
        self._keep_raw(self.renderer.render(grid))
        self.cache.store(frame, grid.smoke.data, grid.temperature.data,
                         tuple(field.data for field in grid.velocity_fields()))
        self.edges[frame] = self._faces_reached(grid.smoke.data)
        if frame == self.frames - 1:
            self._finish()
        return frame

    def _faces_reached(self, smoke: wp.array) -> tuple[str, ...]:
        if self._layers is None:
            side = max(self.derived.cells)
            self._layers = wp.zeros((len(FACE_NAMES), side, side), dtype=float, device=self.device)
        wp.launch(boundary_layer_kernel, dim=self._layers.shape, device=self.device, inputs=[smoke, self._layers])
        return faces_reached(self._layers.numpy(), self.recipe)

    def _keep_raw(self, raw: np.ndarray) -> None:
        self.raw_frames.append(raw)
        self._largest_raw_heat = max(self._largest_raw_heat, float(raw[..., HEAT].max()))

    def _recaptured_frames(self):
        scratch = self.cache.scratch()
        for frame in range(self.frames):
            smoke, temperature = self.cache.load(frame, scratch)
            self._keep_raw(self.renderer.render_fields(smoke, temperature, self.info))
            if frame == self.frames - 1:
                self._start_assembly()
            yield frame

    def cancel(self) -> None:
        """Stops the run where it is; its frames stay drawable."""
        if self.capturing:
            self.stopped = True
            if not self.recaptured:
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
        else:
            self.source = None  # its divisors are no longer needed; let it go
        return True

    def wait_for_assembly(self) -> None:
        """Blocks until the assembly has finished (for tests and scripts)."""
        if self._assembly is not None:
            self._assembly.exception()
            self.poll_assembly()

    @property
    def heat_divisor(self) -> float:
        """What heat 1 means: the sheet's divisor once assembled, else a re-capture's source's, else the
        largest raw heat so far."""
        if self.assembled is None and self.source is not None:
            return self.source.heat_divisor
        divisor = self.assembled.heat_divisor if self.assembled else self._largest_raw_heat
        return divisor if divisor > 0.0 else 1.0

    @property
    def shade_divisor(self) -> float:
        """The sheet's shade divisor once assembled, else a re-capture's source's, else 1."""
        if self.assembled is None and self.source is not None:
            return self.source.shade_divisor
        if self.assembled is None or self.assembled.shade_divisor is None:
            return 1.0
        return self.assembled.shade_divisor

    def _finish(self) -> None:
        try:
            next(self._frames)
        except StopIteration as finished:
            self.steps = finished.value
        self.elapsed_s = time.perf_counter() - self.started_s
        self._start_assembly()

    def _start_assembly(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="plume-assemble")
        self._assembly = self._executor.submit(
            assemble, list(self.raw_frames), self.view, seat_point(self.recipe), self.recipe.output.frame_px,
            self.recipe.render, self.recipe.output.channels)
