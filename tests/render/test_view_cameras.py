"""The ray march's perspective camera, which the viewer uses: it agrees with the orthographic march when
its rays are nearly parallel, and it starts at the eye when the eye is inside the volume."""

import math

import numpy as np
import pytest
import warp as wp

from plume.recipe.schema import SHADE_LAYOUT, RenderSettings
from plume.render.camera import make_camera, make_domain_view
from plume.render.frame_renderer import FrameRenderer, domain_view_params
from plume.render.raw_frame import CHANNELS, HEAT, SHADE, THICKNESS
from support.grids import blob, fill, small_grid
from support.render import CELL_M, CELLS

DISTANCE_M = 200.0


def march(grid, renderer, params, height, width):
    image = wp.zeros((height, width, CHANNELS), dtype=float, device=grid.device)
    renderer.prepare(grid.smoke.data, grid.info.cell_m)
    renderer.march(grid.smoke.data, grid.temperature.data, grid.info, params, image)
    return image.numpy()


def perspective_params(view, distance_m):
    """A perspective camera `distance_m` out along the view's axis whose plane at the world origin matches
    the domain view's pixels: plane coordinates scale by 1 / distance."""
    camera = view.camera
    center_x = view.left_m + view.width_px * view.pixel_m / 2
    center_y = view.top_m - view.height_px * view.pixel_m / 2
    params = domain_view_params(view)
    params.perspective = 1
    params.eye = wp.vec3(*(camera.right * center_x + camera.up * center_y + camera.toward * distance_m))
    params.left_m = (view.left_m - center_x) / distance_m
    params.top_m = (view.top_m - center_y) / distance_m
    params.pixel_m = view.pixel_m / distance_m
    return params


def test_a_far_narrow_perspective_camera_matches_the_orthographic_march(cpu_device):
    grid = small_grid(cpu_device, cells=CELLS, cell_m=CELL_M)
    fill(grid.smoke.data, 3.0 * blob(CELLS, (8.0, 7.0, 9.0), 3.0))
    fill(grid.temperature.data, 293.0 + 900.0 * blob(CELLS, (8.0, 7.0, 9.0), 2.0))
    view = make_domain_view(make_camera(25.0, 40.0), (-0.8, 0.0, -0.8), (1.6, 1.6, 1.6), CELL_M, 2.0)
    renderer = FrameRenderer(view, RenderSettings(), grid.cells, SHADE_LAYOUT, grid.device)
    orthographic = march(grid, renderer, renderer.view_params, view.height_px, view.width_px)
    perspective = march(grid, renderer, perspective_params(view, DISTANCE_M), view.height_px, view.width_px)
    # Measured (Linux CPU): at 200 m the largest differences are 0.0054 in thickness, 0.0041 in shade times
    # thickness and 0.52 percent of the peak heat; at 20 m about ten times that, as rays that spread by
    # 1/distance across the box should.
    assert np.abs(perspective[..., THICKNESS] - orthographic[..., THICKNESS]).max() < 0.01
    assert np.abs(perspective[..., SHADE] - orthographic[..., SHADE]).max() < 0.01
    assert np.abs(perspective[..., HEAT] - orthographic[..., HEAT]).max() < 0.01 * orthographic[..., HEAT].max()
    assert orthographic[..., THICKNESS].max() > 0.9


def test_an_eye_inside_the_smoke_sees_only_the_smoke_in_front_of_it(cpu_device):
    grid = small_grid(cpu_device, cells=CELLS, cell_m=CELL_M)
    fill(grid.smoke.data, np.full(CELLS, 0.5))
    view = make_domain_view(make_camera(0.0, 0.0), (-0.8, 0.0, -0.8), (1.6, 1.6, 1.6), CELL_M, 2.0)
    renderer = FrameRenderer(view, RenderSettings(opacity_per_density=2.0), grid.cells, SHADE_LAYOUT, grid.device)
    params = domain_view_params(view)
    params.perspective = 1
    params.eye = wp.vec3(0.0, 0.8, 0.3)  # 1.1 m from the back wall (z = -0.8), looking along -z
    params.left_m, params.top_m, params.pixel_m = -0.5, 0.5, 1.0 / 9.0
    image = march(grid, renderer, params, 9, 9)
    assert image[4, 4, THICKNESS] == pytest.approx(1.0 - math.exp(-2.0 * 0.5 * 1.1), rel=1e-4)
