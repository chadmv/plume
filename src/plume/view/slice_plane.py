"""The slice plane (`L`, spec V5 and section 4.3): one cached field colored on an axis-aligned plane through
the domain, drawn over the Volume view with the volume dimmed behind it.

`L` cycles the plane off, x, y, z; a plain left drag in the viewport moves it along its axis. The field is
smoke, temperature, speed (`|v|`) or swirl (the vorticity's magnitude, `|curl v|`, with the simulation's own
`curl_kernel`); speed and swirl need the frame's velocity, which the frame cache drops first when its budget
is short.

Each drawn frame's field is prepared once as a 32-bit scalar volume, and the legend's range is that volume's
range over the whole frame (0 to its largest value; temperature from its smallest), so the legend stays put
while the plane moves. The slice kernel casts each pixel's ray with the march's own `pixel_ray`, meets the
plane, and samples the volume trilinearly there: opaque ramp color where the ray meets the plane inside the
domain, the volume's own pixel at `DIM` elsewhere.
"""

from dataclasses import dataclass

import numpy as np
import warp as wp

from plume.render.raymarch import ViewParams, pixel_ray
from plume.sim.grid import GridInfo
from plume.sim.sample import sample_index_space
from plume.sim.vorticity import curl_kernel
from plume.view.live_run import LiveRun
from plume.view.navigation import ViewCamera
from plume.view.viewport import table_lookup, to_byte, view_params

AXIS_NAMES = ("x", "y", "z")
SMOKE, TEMPERATURE, SPEED, SWIRL = "smoke", "temperature", "speed", "swirl"
FIELDS = (SMOKE, TEMPERATURE, SPEED, SWIRL)
VELOCITY_FIELDS = (SPEED, SWIRL)
UNITS = {SMOKE: "", TEMPERATURE: "K", SPEED: "m/s", SWIRL: "1/s"}
DIM = 0.4  # the volume's brightness where the plane does not cover it
# The slice's color ramp, low to high, as display (sRGB) colors: a dark blue through teal and green to yellow
# (perceptually ordered, readable on the dimmed smoke). The kernel's table and the legend both come from it.
RAMP_STOPS = ((0.0, (0.07, 0.04, 0.33)), (0.25, (0.17, 0.33, 0.55)), (0.5, (0.13, 0.57, 0.55)),
              (0.75, (0.37, 0.79, 0.38)), (1.0, (0.99, 0.91, 0.15)))
RAMP_TABLE_SIZE = 256
DIM_VALUE = wp.constant(DIM)
SCREEN_AXIS_MIN_PX = 4.0  # an axis shorter than this many pixels per meter on screen drags by the mouse's height


def ramp_colors(count: int) -> np.ndarray:
    """`count` evenly spaced colors of the ramp, (count, 3) in 0..1."""
    positions = np.linspace(0.0, 1.0, count)
    stops = np.array([stop for stop, _ in RAMP_STOPS])
    colors = np.array([color for _, color in RAMP_STOPS])
    return np.stack([np.interp(positions, stops, colors[:, channel]) for channel in range(3)], axis=-1)


@dataclass
class SlicePlane:
    """The plane's state in the window: its axis (None when off), its place along each axis in world meters,
    and the field it shows."""

    domain_min: np.ndarray
    domain_size: np.ndarray
    axis: int | None = None
    field_name: str = SMOKE
    position_m: np.ndarray | None = None

    def __post_init__(self):
        self.domain_min = np.asarray(self.domain_min, dtype=np.float64)
        self.domain_size = np.asarray(self.domain_size, dtype=np.float64)
        if self.position_m is None:
            self.position_m = self.domain_min + self.domain_size / 2

    def cycle(self) -> None:
        """`L`: off, x, y, z, off."""
        self.axis = 0 if self.axis is None else (None if self.axis == 2 else self.axis + 1)

    @property
    def coordinate_m(self) -> float:
        """Where the plane cuts its axis, in world meters."""
        return float(self.position_m[self.axis])

    def drag(self, dx_px: float, dy_px: float, camera: ViewCamera) -> None:
        """Moves the plane along its axis by a mouse drag: the part of the drag along the axis as it shows on
        screen; an axis seen end on moves by the drag's height (up is toward the viewer), one pixel per
        pixel's size."""
        if self.axis is None:
            return
        axis = np.zeros(3)
        axis[self.axis] = 1.0
        center = self.domain_min + self.domain_size / 2
        center[self.axis] = self.coordinate_m
        start, end = camera.project(center), camera.project(center + axis)
        moved = 0.0
        if start is not None and end is not None:
            screen = np.array(end) - np.array(start)
            length_sq = float(screen @ screen)
            if length_sq >= SCREEN_AXIS_MIN_PX**2:
                moved = float(np.array([dx_px, dy_px]) @ screen) / length_sq
            else:
                start = None
        if start is None or end is None:
            meters_per_px = camera.pixel * (camera.ahead(center) if camera.perspective else 1.0)
            moved = -dy_px * meters_per_px
        low = self.domain_min[self.axis]
        self.position_m[self.axis] = min(max(self.coordinate_m + moved, low), low + self.domain_size[self.axis])


@wp.kernel
def speed_kernel(velocity: wp.array3d(dtype=wp.vec3), out: wp.array3d(dtype=float)):
    i, j, k = wp.tid()
    out[i, j, k] = wp.length(velocity[i, j, k])


@wp.kernel
def slice_kernel(view: ViewParams, info: GridInfo, axis: int, coordinate_m: float, values: wp.array3d(dtype=float),
                 low: float, high: float, ramp: wp.array(dtype=wp.vec3), image: wp.array3d(dtype=wp.uint8)):
    """Colors each pixel whose ray meets the plane `axis = coordinate_m` inside the domain by the field
    there; dims the rest. `image` is the volume's display bytes, (height, width, 4), changed in place."""
    py, px = wp.tid()
    origin, direction = pixel_ray(view, px, py)
    hit = int(0)
    position = wp.vec3(0.0, 0.0, 0.0)
    if wp.abs(direction[axis]) > 1.0e-9:
        distance = (coordinate_m - origin[axis]) / direction[axis]
        if view.perspective == 0 or distance > 0.0:
            position = origin + direction * distance
            hit = 1
            for other in range(3):
                extent = float(info.dims[other]) * info.cell_m
                if other != axis and (position[other] < info.origin_m[other]
                                      or position[other] > info.origin_m[other] + extent):
                    hit = 0
    if hit == 1:
        g = (position - info.origin_m) / info.cell_m - wp.vec3(0.5, 0.5, 0.5)
        color = table_lookup(ramp, (sample_index_space(values, g) - low) / (high - low))
        image[py, px, 0] = to_byte(color[0])
        image[py, px, 1] = to_byte(color[1])
        image[py, px, 2] = to_byte(color[2])
    else:
        for channel in range(3):
            image[py, px, channel] = to_byte(float(image[py, px, channel]) / 255.0 * DIM_VALUE)


class SliceDrawer:
    """One viewport's slice: the prepared field of the drawn frame (kept while the frame and field stay)
    and the ramp table. Its scratch arrays are its own, apart from the viewport's."""

    def __init__(self, device: str):
        self.device = device
        self.ramp = wp.array(ramp_colors(RAMP_TABLE_SIZE).astype(np.float32), dtype=wp.vec3, device=device)
        self._prepared: tuple | None = None
        self._values: wp.array | None = None
        self.range: tuple[float, float] = (0.0, 1.0)
        self._scratch: dict = {}

    def prepare(self, run: LiveRun, frame: int, field_name: str) -> bool:
        """Readies the field of a kept frame; False when the frame has no velocity for speed or swirl."""
        key = (run.serial, frame, field_name)
        if self._prepared == key:
            return True
        cache = run.cache
        if field_name in VELOCITY_FIELDS and not cache.velocity_kept(frame):
            return False
        if self._scratch.get("cache") is not cache:
            self._scratch = {"cache": cache, "pair": cache.scratch()}
        if field_name in (SMOKE, TEMPERATURE):
            smoke, temperature = cache.load(frame, self._scratch["pair"])
            values = smoke if field_name == SMOKE else temperature
        else:
            if "velocity" not in self._scratch:
                self._scratch["velocity"] = cache.velocity_scratch()
                self._scratch["vectors"] = wp.zeros(cache.cells, dtype=wp.vec3, device=self.device)
                self._scratch["scalar"] = wp.zeros(cache.cells, dtype=float, device=self.device)
            velocity = cache.load_velocity(frame, self._scratch["velocity"])
            if field_name == SWIRL:
                wp.launch(curl_kernel, dim=cache.cells, device=self.device,
                          inputs=[velocity, self._scratch["vectors"], run.info])
                velocity = self._scratch["vectors"]
            values = self._scratch["scalar"]
            wp.launch(speed_kernel, dim=cache.cells, device=self.device, inputs=[velocity, values])
        self._values = values
        self.range = field_range(values.numpy(), field_name)
        self._prepared = key
        return True

    def overlay(self, image: wp.array, camera: ViewCamera, run: LiveRun, plane: SlicePlane) -> None:
        """Draws the prepared field on the plane over the volume's display bytes (on the device)."""
        low, high = self.range
        wp.launch(slice_kernel, dim=image.shape[:2], device=self.device,
                  inputs=[view_params(camera), run.info, plane.axis, plane.coordinate_m, self._values, low, high,
                          self.ramp, image])


def field_range(values: np.ndarray, field_name: str) -> tuple[float, float]:
    """The legend's range for a field's values: 0 to the largest (temperature from its smallest), never
    empty."""
    high = float(values.max()) if values.size else 1.0
    low = float(values.min()) if field_name == TEMPERATURE and values.size else 0.0
    if not high > low:
        high = low + 1.0
    return low, high
