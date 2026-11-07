"""Renders a grid's current state into a raw frame image over the domain view."""

import numpy as np
import warp as wp

from plume.recipe.schema import RenderSettings
from plume.render.camera import DomainView
from plume.render.normal_field import NormalField
from plume.render.raw_frame import CHANNELS
from plume.render.raymarch import LookParams, ViewParams, raymarch_kernel
from plume.sim.grid import Grid


class FrameRenderer:
    """Holds the per-run render state (view, settings, scratch arrays) and renders one frame at a time."""

    def __init__(self, view: DomainView, settings: RenderSettings, cells: tuple[int, int, int], device: str):
        self.device = device
        self.view_params = _view_params(view)
        self.look_params = _look_params(settings)
        self.normal_field = NormalField(cells, settings.normal_blur_cells, device)
        self.image = wp.zeros((view.height_px, view.width_px, CHANNELS), dtype=float, device=device)

    def render(self, grid: Grid) -> np.ndarray:
        """The raw frame image of the grid's current smoke and temperature, copied to the host."""
        gradient = self.normal_field.compute(grid.smoke.data)
        wp.launch(raymarch_kernel, dim=self.image.shape[:2], device=self.device,
                  inputs=[grid.smoke.data, grid.temperature.data, gradient, grid.info, self.view_params,
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


def _look_params(settings: RenderSettings) -> LookParams:
    params = LookParams()
    params.opacity_per_density = settings.opacity_per_density
    params.glow_start_k = settings.glow_start_k
    params.smoke_hides_heat = settings.smoke_hides_heat
    params.normal_fade_thickness = settings.normal_fade_thickness
    return params
