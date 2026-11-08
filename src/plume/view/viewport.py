"""Drawing the Volume view: one kept frame, from the viewer's camera, as an RGBA8 image.

Steps: widen the cached frame to 32 bits, run the layout's volume pass (the light volume or the normal
field, kept while the drawn frame stays the same), march every pixel with the sheet's ray march, then turn
the raw march image into display bytes on the device by view:
- Look: the contact sheets' composite (`report/composite.py`) over a background, in sRGB;
- Heat, Thickness, Shade: the channel as a gray byte, as the channel strip shows it;
- Normal (the normal layout's fourth view): `(n + 1) / 2` as RGB.

The composite's two formula lines are written here a second time, for the device; its ramps and sRGB curve
are tabulated from `report/color.py` itself, and a test holds the two composites equal. Heat is divided by
the run's heat divisor and the shade by its shade divisor, as the sheet's are.
"""

import math

import numpy as np
import warp as wp

from plume.recipe.derived import Derived
from plume.recipe.schema import SHADE_LAYOUT, Recipe
from plume.render.camera import sheet_domain_view
from plume.render.frame_renderer import FrameRenderer, toward_light_world
from plume.render.raw_frame import CHANNELS, HEAT, NORMAL_X, NORMAL_Y, NORMAL_Z, SHADE, THICKNESS
from plume.render.raymarch import FAR_M, ViewParams, slab_range
from plume.report.color import hex_to_linear, linear_to_srgb, ramp
from plume.sheet.shade import NO_SMOKE
from plume.sim.grid import GridInfo
from plume.sim.sample import sample_index_space
from plume.view.live_run import LiveRun
from plume.view.navigation import ViewCamera

LOOK, HEAT_VIEW, THICKNESS_VIEW, SHADE_VIEW = 0, 1, 2, 3  # keys 1 to 4; SHADE_VIEW shows the normal layout's normal
DARK_BACKGROUND = "#303030"
RAMP_TABLE_SIZE = 1024
SRGB_TABLE_SIZE = 16384
RELEASE_THICKNESS = 0.5  # the right-mouse release puts the pivot where the center ray's thickness passes this

_HEAT = wp.constant(HEAT)
_THICKNESS = wp.constant(THICKNESS)
_SHADE = wp.constant(SHADE)
_NORMAL_X = wp.constant(NORMAL_X)
_NORMAL_Y = wp.constant(NORMAL_Y)
_NORMAL_Z = wp.constant(NORMAL_Z)
_NO_SMOKE = wp.constant(NO_SMOKE)


@wp.struct
class LookInputs:
    view: int
    shade_layout: int
    heat_divisor: float
    shade_divisor: float
    shade_depth: float
    ambient: float
    toward_light: wp.vec3  # in the drawn camera's space
    background: wp.vec3  # linear RGB


@wp.func
def table_lookup(table: wp.array(dtype=wp.vec3), value: float) -> wp.vec3:
    """Linear interpolation in a ramp tabulated at evenly spaced values from 0 to 1."""
    position = wp.clamp(value, 0.0, 1.0) * float(table.shape[0] - 1)
    low = wp.min(int(position), table.shape[0] - 2)
    return wp.lerp(table[low], table[low + 1], position - float(low))


@wp.func
def to_byte(value: float) -> wp.uint8:
    return wp.uint8(int(wp.clamp(wp.floor(value * 255.0 + 0.5), 0.0, 255.0)))


@wp.func
def srgb_byte(table: wp.array(dtype=wp.uint8), linear: float) -> wp.uint8:
    return table[int(wp.clamp(linear, 0.0, 1.0) * float(table.shape[0] - 1) + 0.5)]


@wp.kernel
def look_kernel(raw: wp.array3d(dtype=float), smoke_ramp: wp.array(dtype=wp.vec3),
                emission_ramp: wp.array(dtype=wp.vec3), srgb: wp.array(dtype=wp.uint8), inputs: LookInputs,
                out: wp.array3d(dtype=wp.uint8)):
    py, px = wp.tid()
    heat = wp.clamp(raw[py, px, _HEAT] / inputs.heat_divisor, 0.0, 1.0)
    thickness = wp.clamp(raw[py, px, _THICKNESS], 0.0, 1.0)
    normal = wp.vec3(raw[py, px, _NORMAL_X], raw[py, px, _NORMAL_Y], raw[py, px, _NORMAL_Z])
    shade = float(0.0)
    light = float(1.0)
    if inputs.shade_layout == 1:
        if thickness > _NO_SMOKE:
            shade = wp.clamp(raw[py, px, _SHADE] / thickness / inputs.shade_divisor, 0.0, 1.0)
        light = 1.0 - inputs.shade_depth * (1.0 - shade)
    else:
        light = inputs.ambient + (1.0 - inputs.ambient) * wp.max(0.0, wp.dot(normal, inputs.toward_light))
    color = wp.vec3(0.0, 0.0, 0.0)
    if inputs.view == 0:
        smoke = wp.cw_mul(table_lookup(smoke_ramp, heat), wp.vec3(light, light, light))
        linear = inputs.background * (1.0 - thickness) + smoke * thickness + table_lookup(emission_ramp, heat)
        out[py, px, 0] = srgb_byte(srgb, linear[0])
        out[py, px, 1] = srgb_byte(srgb, linear[1])
        out[py, px, 2] = srgb_byte(srgb, linear[2])
    else:
        gray = heat
        if inputs.view == 2:
            gray = thickness
        elif inputs.view == 3:
            gray = shade
        color = wp.vec3(gray, gray, gray)
        if inputs.view == 3 and inputs.shade_layout == 0:
            color = (normal + wp.vec3(1.0, 1.0, 1.0)) * 0.5
        out[py, px, 0] = to_byte(color[0])
        out[py, px, 1] = to_byte(color[1])
        out[py, px, 2] = to_byte(color[2])
    out[py, px, 3] = wp.uint8(255)


@wp.kernel
def center_depth_kernel(smoke: wp.array3d(dtype=float), info: GridInfo, origin: wp.vec3, direction: wp.vec3,
                        opacity_per_density: float, threshold: float, result: wp.array(dtype=float)):
    """The distance along one ray at which the march's thickness first reaches `threshold`; -1 if never."""
    box_max = info.origin_m + wp.vec3(float(info.dims[0]), float(info.dims[1]), float(info.dims[2])) * info.cell_m
    span = slab_range(origin, direction, info.origin_m, box_max)
    start = wp.max(span[0], 0.0)
    found = float(-1.0)
    if span[1] > start:
        length = span[1] - start
        steps = int(wp.ceil(length / (0.5 * info.cell_m)))
        step_m = length / float(steps)
        transmittance = float(1.0)
        for s in range(steps):
            distance = start + (float(s) + 0.5) * step_m
            g = (origin + direction * distance - info.origin_m) / info.cell_m - wp.vec3(0.5, 0.5, 0.5)
            density = wp.max(sample_index_space(smoke, g), 0.0)
            transmittance = transmittance * wp.exp(-opacity_per_density * density * step_m)
            if found < 0.0 and 1.0 - transmittance >= threshold:
                found = distance
    result[0] = found


def view_params(camera: ViewCamera) -> ViewParams:
    """The ray march's view for a viewer camera."""
    params = ViewParams()
    params.right = wp.vec3(*camera.right)
    params.up = wp.vec3(*camera.up)
    params.toward = wp.vec3(*camera.toward)
    params.left_m = camera.left
    params.top_m = camera.top
    params.pixel_m = camera.pixel
    params.perspective = 1 if camera.perspective else 0
    params.eye = wp.vec3(*camera.eye)
    return params


class LookTables:
    """The composite's ramps and sRGB curve, tabulated on the device from `report/color.py`."""

    def __init__(self, recipe: Recipe, device: str):
        positions = np.linspace(0.0, 1.0, RAMP_TABLE_SIZE)
        self.smoke_ramp = wp.array(ramp(recipe.look.smoke_ramp, positions).astype(np.float32), dtype=wp.vec3,
                                   device=device)
        self.emission_ramp = wp.array(ramp(recipe.look.emission_ramp, positions).astype(np.float32),
                                      dtype=wp.vec3, device=device)
        srgb = np.floor(linear_to_srgb(np.linspace(0.0, 1.0, SRGB_TABLE_SIZE)) * 255.0 + 0.5)
        self.srgb = wp.array(srgb.astype(np.uint8), dtype=wp.uint8, device=device)


def look_inputs(recipe: Recipe, view: int, heat_divisor: float, shade_divisor: float, background_hex: str,
                toward_light_camera: np.ndarray) -> LookInputs:
    inputs = LookInputs()
    inputs.view = view
    inputs.shade_layout = 1 if recipe.output.channels == SHADE_LAYOUT else 0
    inputs.heat_divisor = heat_divisor if heat_divisor > 0.0 else 1.0
    inputs.shade_divisor = shade_divisor if shade_divisor > 0.0 else 1.0
    inputs.shade_depth = recipe.look.shade_depth
    inputs.ambient = recipe.look.ambient
    inputs.toward_light = wp.vec3(*toward_light_camera)
    inputs.background = wp.vec3(*hex_to_linear(background_hex))
    return inputs


def shade_bytes(raw: np.ndarray, recipe: Recipe, tables: LookTables, inputs: LookInputs, device: str) -> np.ndarray:
    """The look kernel over a host raw image: (height, width, 4) uint8."""
    raw_device = wp.array(raw.astype(np.float32), dtype=float, device=device)
    out = wp.zeros((*raw.shape[:2], 4), dtype=wp.uint8, device=device)
    wp.launch(look_kernel, dim=raw.shape[:2], device=device,
              inputs=[raw_device, tables.smoke_ramp, tables.emission_ramp, tables.srgb, inputs, out])
    return out.numpy()


class Viewport:
    """Draws a live run's kept frames for any camera. Holds the march's scratch images by size."""

    def __init__(self, recipe: Recipe, derived: Derived, device: str):
        self.recipe = recipe
        self.device = device
        sheet_view = sheet_domain_view(recipe, derived)
        self.renderer = FrameRenderer(sheet_view, recipe.render, derived.cells, recipe.output.channels, device)
        light = toward_light_world(sheet_view.camera, recipe.render.light_dir)
        self.toward_light_world = light / np.linalg.norm(light)
        self.tables = LookTables(recipe, device)
        self._prepared: tuple[int, int] | None = None  # (run, frame) the loaded fields and volume pass hold
        self._images: dict[tuple[int, int], tuple[wp.array, wp.array]] = {}
        self._depth = wp.zeros(1, dtype=float, device=device)

    def draw(self, run: LiveRun, frame: int, camera: ViewCamera, view: int, background_hex: str) -> np.ndarray:
        """A kept frame of the run from `camera`: (height, width, 4) uint8 RGBA."""
        smoke, temperature = self._load(run, frame)
        raw, out = self._image(camera.height_px, camera.width_px)
        self.renderer.march(smoke, temperature, run.info, view_params(camera), raw)
        light = np.array([self.toward_light_world @ camera.right, self.toward_light_world @ camera.up,
                          self.toward_light_world @ camera.toward])
        inputs = look_inputs(self.recipe, view, run.heat_divisor, run.shade_divisor, background_hex, light)
        wp.launch(look_kernel, dim=raw.shape[:2], device=self.device,
                  inputs=[raw, self.tables.smoke_ramp, self.tables.emission_ramp, self.tables.srgb, inputs, out])
        return out.numpy().copy()  # on the CPU device numpy() shares the array the next draw overwrites

    def center_hit(self, run: LiveRun, frame: int, camera: ViewCamera) -> np.ndarray | None:
        """The first point along the view's center ray where the smoke's thickness passes one half, in
        world meters; None when the ray never gets there."""
        smoke, _ = self._load(run, frame)
        direction = -camera.toward
        if camera.perspective:
            origin = camera.eye
        else:
            center_x = camera.left + camera.pixel * camera.width_px / 2
            center_y = camera.top - camera.pixel * camera.height_px / 2
            origin = camera.right * center_x + camera.up * center_y + camera.toward * FAR_M
        wp.launch(center_depth_kernel, dim=1, device=self.device,
                  inputs=[smoke, run.info, wp.vec3(*origin), wp.vec3(*direction),
                          self.recipe.render.opacity_per_density, RELEASE_THICKNESS, self._depth])
        distance = float(self._depth.numpy()[0])
        return None if distance < 0.0 else origin + direction * distance

    def smoke_on_host(self, run: LiveRun, frame: int) -> np.ndarray:
        """A kept frame's 32-bit smoke, copied to the host (for F's framing)."""
        return self._load(run, frame)[0].numpy().copy()

    def visible_density(self) -> float:
        """Smoke density at which one cell's opacity reaches one byte step (1/255)."""
        cell_m = self.recipe.domain.cell_m
        return -math.log(1.0 - 1.0 / 255.0) / (self.recipe.render.opacity_per_density * cell_m)

    def _load(self, run: LiveRun, frame: int) -> tuple[wp.array, wp.array]:
        smoke, temperature = run.cache.load(frame)
        key = (id(run), frame)
        if self._prepared != key:
            self.renderer.prepare(smoke, run.info.cell_m)
            self._prepared = key
        return smoke, temperature

    def _image(self, height: int, width: int) -> tuple[wp.array, wp.array]:
        if (height, width) not in self._images:
            if len(self._images) > 4:
                self._images.clear()
            self._images[(height, width)] = (
                wp.zeros((height, width, CHANNELS), dtype=float, device=self.device),
                wp.zeros((height, width, 4), dtype=wp.uint8, device=self.device))
        return self._images[(height, width)]
