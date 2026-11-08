"""Renders a grid's current state into a raw frame image over the domain view."""

import numpy as np
import warp as wp

from plume.recipe.schema import SHADE_LAYOUT, RenderSettings
from plume.render.camera import DomainView
from plume.render.light_volume import LightVolume
from plume.render.normal_field import NormalField
from plume.render.raw_frame import CHANNELS
from plume.render.raymarch import LookParams, ViewParams, raymarch_kernel
from plume.sim.grid import Grid


class FrameRenderer:
    """Holds the per-run render state (view, settings, scratch arrays) and renders one frame at a time.

    The sheet's channel layout picks the per-frame volume pass: the light volume for the shade layout, the
    normal field for the normal layout. The other pass is never run; the kernel gets a one-cell stand-in.
    """

    def __init__(self, view: DomainView, settings: RenderSettings, cells: tuple[int, int, int], channels: str,
                 device: str):
        self.device = device
        self.shade_layout = channels == SHADE_LAYOUT
        self.view_params = _view_params(view)
        self.look_params = _look_params(settings, self.shade_layout)
        if self.shade_layout:
            camera = view.camera
            x, y, z = settings.light_dir
            toward_light_world = x * camera.right + y * camera.up + z * camera.toward
            self.light_volume = LightVolume(cells, toward_light_world, settings.opacity_per_density, device)
            self.unused_gradient = wp.zeros((1, 1, 1), dtype=wp.vec3, device=device)
        else:
            self.normal_field = NormalField(cells, settings.normal_blur_cells, device)
            self.unused_light = wp.zeros((1, 1, 1), dtype=float, device=device)
        self.image = wp.zeros((view.height_px, view.width_px, CHANNELS), dtype=float, device=device)

    def render(self, grid: Grid) -> np.ndarray:
        """The raw frame image of the grid's current smoke and temperature, copied to the host."""
        if self.shade_layout:
            gradient = self.unused_gradient
            light = self.light_volume.compute(grid)
        else:
            gradient = self.normal_field.compute(grid.smoke.data)
            light = self.unused_light
        wp.launch(raymarch_kernel, dim=self.image.shape[:2], device=self.device,
                  inputs=[grid.smoke.data, grid.temperature.data, gradient, light, grid.info, self.view_params,
                          self.look_params, self.image])
        return self.image.numpy().copy()


def _view_params(view: DomainView) -> ViewParams:
    params = ViewParams()
    params.right = wp.vec3(*view.camera.right)
    params.up = wp.vec3(*view.camera.up)
    params.toward = wp.vec3(*view.camera.toward)
    params.left_m = view.left_m
    params.top_m = view.top_m
    params.pixel_m = view.pixel_m
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
