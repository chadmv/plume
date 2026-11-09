"""Renders smoke and temperature fields into a raw frame image: the sheet's domain view, or any view the
viewer asks for."""

import numpy as np
import warp as wp

from plume.recipe.schema import SHADE_LAYOUT, RenderSettings
from plume.render.camera import Camera, DomainView
from plume.render.light_volume import LightVolume
from plume.render.normal_field import NormalField
from plume.render.raw_frame import CHANNELS
from plume.render.raymarch import LookParams, ViewParams, raymarch_kernel
from plume.sim.grid import Grid, GridInfo


class FrameRenderer:
    """Holds the per-run render state (view, settings, scratch arrays) and renders one frame at a time.

    The sheet's channel layout picks the per-frame volume pass: the light volume for the shade layout, the
    normal field for the normal layout. The other pass is never run; the kernel gets a one-cell stand-in.
    """

    def __init__(self, view: DomainView, settings: RenderSettings, cells: tuple[int, int, int], channels: str,
                 device: str):
        self.device = device
        self.shade_layout = channels == SHADE_LAYOUT
        self.view_params = domain_view_params(view)
        self.look_params = _look_params(settings, self.shade_layout)
        if self.shade_layout:
            light_world = toward_light_world(view.camera, settings.light_dir)
            self.light_volume = LightVolume(cells, light_world, settings.opacity_per_density, device)
            self.gradient = wp.zeros((1, 1, 1), dtype=wp.vec3, device=device)
        else:
            self.normal_field = NormalField(cells, settings.normal_blur_cells, device)
            self.light = wp.zeros((1, 1, 1), dtype=float, device=device)
        self.image = wp.zeros((view.height_px, view.width_px, CHANNELS), dtype=float, device=device)

    def render(self, grid: Grid) -> np.ndarray:
        """The raw frame image of the grid's current smoke and temperature over the domain view, copied to
        the host."""
        self.prepare(grid.smoke.data, grid.info.cell_m)
        self.march(grid.smoke.data, grid.temperature.data, grid.info, self.view_params, self.image)
        return self.image.numpy().copy()

    def prepare(self, smoke: wp.array, cell_m: float) -> None:
        """Runs the layout's volume pass (light volume or normal field) on a smoke field. `march` reads its
        result until the next call, so a viewer can march many views of one frame after one pass."""
        if self.shade_layout:
            self.light = self.light_volume.compute(smoke, cell_m)
        else:
            self.gradient = self.normal_field.compute(smoke)

    def march(self, smoke: wp.array, temperature: wp.array, info: GridInfo, view: ViewParams,
              image: wp.array) -> None:
        """Marches every pixel of `image` ((height, width, CHANNELS) float, on the device) through the
        fields for `view`, with the volume pass of the last `prepare` on the same smoke."""
        wp.launch(raymarch_kernel, dim=image.shape[:2], device=self.device,
                  inputs=[smoke, temperature, self.gradient, self.light, info, view, self.look_params, image])


def toward_light_world(camera: Camera, light_dir: tuple[float, float, float]) -> np.ndarray:
    """The world direction toward the key light: `render.light_dir` is in the sheet camera's space."""
    x, y, z = light_dir
    return x * camera.right + y * camera.up + z * camera.toward


def domain_view_params(view: DomainView) -> ViewParams:
    """The march's view for a domain view: the sheet's orthographic camera over its pixels."""
    params = ViewParams()
    params.right = wp.vec3(*view.camera.right)
    params.up = wp.vec3(*view.camera.up)
    params.toward = wp.vec3(*view.camera.toward)
    params.left_m = view.left_m
    params.top_m = view.top_m
    params.pixel_m = view.pixel_m
    params.perspective = 0
    params.eye = wp.vec3(0.0, 0.0, 0.0)
    return params


def _look_params(settings: RenderSettings, shade_layout: bool) -> LookParams:
    params = LookParams()
    params.opacity_per_density = settings.opacity_per_density
    params.glow_start_k = settings.glow_start_k
    params.smoke_hides_heat = settings.smoke_hides_heat
    params.normal_fade_thickness = settings.normal_fade_thickness
    params.shade_layout = 1 if shade_layout else 0
    params.shade_fill = settings.shade_fill
    return params
