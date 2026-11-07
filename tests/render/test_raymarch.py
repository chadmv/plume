import math

import numpy as np
import pytest

from plume.recipe.schema import RenderSettings
from plume.render.camera import make_camera, make_domain_view
from plume.render.frame_renderer import FrameRenderer
from plume.render.raw_frame import HEAT, NORMAL_X, NORMAL_Y, NORMAL_Z, THICKNESS
from support.grids import blob, fill, small_grid

CELL_M = 0.1
CELLS = (16, 16, 16)


def render(grid, elevation_deg=0.0, **settings):
    view = make_domain_view(make_camera(elevation_deg, 0.0), (-0.8, 0.0, -0.8), (1.6, 1.6, 1.6), CELL_M, 2.0)
    renderer = FrameRenderer(view, RenderSettings(**settings), grid.cells, grid.device)
    return view, renderer.render(grid)


def test_domain_view_covers_the_box_at_two_pixels_per_cell():
    view = make_domain_view(make_camera(0.0, 0.0), (-0.8, 0.0, -0.8), (1.6, 1.6, 1.6), CELL_M, 2.0)
    assert (view.width_px, view.height_px) == (32, 32)
    assert view.to_pixels(np.array([-0.8, 1.6, 0.0])) == pytest.approx((0.0, 0.0))


def test_uniform_slab_thickness_follows_beer_lambert(cpu_device):
    grid = small_grid(cpu_device, cells=CELLS, cell_m=CELL_M)
    fill(grid.smoke.data, np.full(CELLS, 0.5))
    _, image = render(grid, opacity_per_density=2.0)
    expected = 1.0 - math.exp(-2.0 * 0.5 * 1.6)
    assert image[16, 16, THICKNESS] == pytest.approx(expected, rel=0.01)


def test_sphere_normals_point_outward_and_face_the_camera_at_the_center(cpu_device):
    grid = small_grid(cpu_device, cells=CELLS, cell_m=CELL_M)
    fill(grid.smoke.data, 3.0 * (blob(CELLS, (8.0, 8.0, 8.0), 3.0) > 0.3))
    _, image = render(grid)
    assert image[16, 16, NORMAL_Z] > 0.95
    assert image[16, 7, NORMAL_X] < -0.5  # left edge faces left
    assert image[7, 16, NORMAL_Y] > 0.5  # top edge faces up (row 0 is the top)


def test_empty_space_faces_the_camera(cpu_device):
    grid = small_grid(cpu_device, cells=CELLS, cell_m=CELL_M)
    _, image = render(grid)
    assert np.allclose(image[..., NORMAL_Z], 1.0)
    assert np.all(image[..., THICKNESS] == 0.0)


def hot_cell_behind_smoke(device):
    grid = small_grid(device, cells=CELLS, cell_m=CELL_M)
    temperature = np.full(CELLS, 293.0)
    temperature[7:9, 7:9, 2:4] = 1200.0  # far from the camera (low z)
    smoke = np.zeros(CELLS)
    smoke[:, :, 10:14] = 20.0  # a dense wall near the camera (high z)
    fill(grid.temperature.data, temperature)
    fill(grid.smoke.data, smoke)
    return grid


def test_smoke_in_front_hides_heat(cpu_device):
    _, hidden = render(hot_cell_behind_smoke(cpu_device), smoke_hides_heat=1.0)
    _, shown = render(hot_cell_behind_smoke(cpu_device), smoke_hides_heat=0.0)
    assert shown[16, 16, HEAT] > 10.0
    assert hidden[16, 16, HEAT] < 0.01 * shown[16, 16, HEAT]


def test_looking_straight_down_shows_the_back_at_the_top(cpu_device):
    grid = small_grid(cpu_device, cells=CELLS, cell_m=CELL_M)
    smoke = np.zeros(CELLS)
    smoke[6:10, 6:10, 1:4] = 2.0  # near the back face (low z)
    fill(grid.smoke.data, smoke)
    view, image = render(grid, elevation_deg=90.0)
    rows = np.nonzero(image[..., THICKNESS].max(axis=1) > 0.1)[0]
    assert (view.width_px, view.height_px) == (32, 32)
    assert rows.max() < 16
