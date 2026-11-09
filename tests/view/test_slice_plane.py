"""The slice plane: the kernel samples the field where each pixel's ray meets the plane, dims the rest; speed
and swirl from the cached velocity; the plane's drag along its axis."""

from types import SimpleNamespace

import numpy as np
import pytest
import warp as wp

from plume.sim.grid import GridInfo
from plume.view.frame_cache import FrameCache
from plume.view.navigation import ViewCamera
from plume.view.slice_plane import (DIM, RAMP_TABLE_SIZE, SMOKE, SPEED, SWIRL, TEMPERATURE, SliceDrawer, SlicePlane,
                                    field_range, ramp_colors)

CELLS = (8, 6, 4)
CELL_M = 0.1


def grid_info(cells=CELLS, cell_m=CELL_M):
    info = GridInfo()
    info.dims = wp.vec3i(*cells)
    info.cell_m = cell_m
    info.origin_m = wp.vec3(0.0, 0.0, 0.0)
    info.open_lo = wp.vec3i(0, 0, 0)
    info.open_hi = wp.vec3i(0, 0, 0)
    info.fill_hi = wp.vec3(1.0, 1.0, 1.0)
    info.ghost_gap = 0.5
    return info


def front_camera(width_px=16, height_px=12, pixel=0.05, left=0.0, top=0.6):
    """Orthographic, looking down -z (toward the viewer is +z), x right, y up."""
    return ViewCamera(right=np.array([1.0, 0.0, 0.0]), up=np.array([0.0, 1.0, 0.0]), toward=np.array([0.0, 0.0, 1.0]),
                      eye=np.array([0.0, 0.0, 10.0]), perspective=False, left=left, top=top, pixel=pixel,
                      width_px=width_px, height_px=height_px)


def fake_run(cache):
    return SimpleNamespace(serial=1, cache=cache, info=grid_info())


def expected_color(normalized):
    table = ramp_colors(RAMP_TABLE_SIZE).astype(np.float32)
    position = np.clip(normalized, 0.0, 1.0) * (RAMP_TABLE_SIZE - 1)
    low = np.minimum(position.astype(int), RAMP_TABLE_SIZE - 2)
    color = table[low] + (table[low + 1] - table[low]) * (position - low)[..., None]
    return np.clip(np.floor(color * 255.0 + 0.5), 0, 255).astype(np.uint8)


def test_the_kernel_samples_the_field_on_the_plane_and_dims_the_rest(cpu_device):
    nx, ny, nz = CELLS
    smoke = np.broadcast_to(np.arange(nx, dtype=np.float32)[:, None, None], CELLS).copy()  # smoke = x index
    zeros = wp.array(np.zeros(CELLS, dtype=np.float32), dtype=float, device=cpu_device)
    cache = FrameCache(CELLS, frames=1, budget_bytes=1e9, device=cpu_device)
    cache.store(0, wp.array(smoke, dtype=float, device=cpu_device), zeros)
    run = fake_run(cache)
    drawer = SliceDrawer(cpu_device)
    assert drawer.prepare(run, 0, SMOKE)
    assert drawer.range == (0.0, float(nx - 1))
    plane = SlicePlane(np.zeros(3), np.array(CELLS) * CELL_M)
    plane.cycle(), plane.cycle(), plane.cycle()
    assert plane.axis == 2
    camera = front_camera()  # 16 x 12 pixels of 5 cm from (0, 0.6): wider than the 0.8 x 0.6 m domain
    gray = np.full((12, 16, 4), 200, dtype=np.uint8)
    image = wp.array(gray, dtype=wp.uint8, device=cpu_device)
    drawer.overlay(image, camera, run, plane)
    got = image.numpy()
    x_m = (np.arange(16) + 0.5) * 0.05
    inside = x_m <= 0.8
    normalized = np.clip(x_m / CELL_M - 0.5, 0.0, nx - 1) / (nx - 1)
    expected = expected_color(normalized)
    for py in range(12):
        assert np.array_equal(got[py, inside, :3], expected[inside])
        assert np.all(got[py, ~inside, :3] == int(np.floor(200 / 255 * DIM * 255 + 0.5)))
    assert np.all(got[..., 3] == 200)  # alpha untouched


def test_speed_and_swirl_of_a_solid_rotation(cpu_device):
    nx, ny, nz = CELLS
    omega = 3.0
    j = np.arange(ny)[None, :, None] + 0.5
    i = np.arange(nx)[:, None, None] + 0.5
    u = np.broadcast_to(-omega * j * CELL_M, (nx + 1, ny, nz)).astype(np.float32).copy()
    v = np.broadcast_to(omega * i * CELL_M, (nx, ny + 1, nz)).astype(np.float32).copy()
    w = np.zeros((nx, ny, nz + 1), dtype=np.float32)
    zeros = wp.array(np.zeros(CELLS, dtype=np.float32), dtype=float, device=cpu_device)
    cache = FrameCache(CELLS, frames=1, budget_bytes=1e9, device=cpu_device)
    cache.store(0, zeros, zeros, tuple(wp.array(a, dtype=float, device=cpu_device) for a in (u, v, w)))
    run = fake_run(cache)
    drawer = SliceDrawer(cpu_device)
    assert drawer.prepare(run, 0, SWIRL)
    assert drawer._values.numpy() == pytest.approx(np.full(CELLS, 2.0 * omega), rel=2e-3)
    assert drawer.prepare(run, 0, SPEED)
    speed = omega * CELL_M * np.sqrt(i**2 + j**2) * np.ones(CELLS)
    assert drawer._values.numpy() == pytest.approx(speed, rel=2e-3)


def test_speed_needs_the_frames_velocity(cpu_device):
    zeros = wp.array(np.zeros(CELLS, dtype=np.float32), dtype=float, device=cpu_device)
    cache = FrameCache(CELLS, frames=1, budget_bytes=1e9, device=cpu_device)
    cache.store(0, zeros, zeros)  # no velocity given
    drawer = SliceDrawer(cpu_device)
    assert not drawer.prepare(fake_run(cache), 0, SPEED)
    assert drawer.prepare(fake_run(cache), 0, TEMPERATURE)


def test_the_legends_range():
    values = np.array([300.0, 900.0, 450.0])
    assert field_range(values, TEMPERATURE) == (300.0, 900.0)
    assert field_range(values, SMOKE) == (0.0, 900.0)
    assert field_range(np.zeros(3), SMOKE) == (0.0, 1.0)


def test_l_cycles_off_x_y_z_off():
    plane = SlicePlane(np.zeros(3), np.ones(3))
    seen = []
    for _ in range(5):
        plane.cycle()
        seen.append(plane.axis)
    assert seen == [0, 1, 2, None, 0]


def test_a_drag_moves_the_plane_along_its_axis_as_it_shows_on_screen():
    plane = SlicePlane(np.zeros(3), np.array([0.8, 0.6, 0.4]))
    plane.cycle()  # x
    camera = front_camera()  # 20 pixels a meter
    plane.drag(4.0, 7.0, camera)  # 4 px right is 0.2 m along x; the vertical part does not count
    assert plane.coordinate_m == pytest.approx(0.6)
    plane.drag(100.0, 0.0, camera)
    assert plane.coordinate_m == pytest.approx(0.8)  # held inside the domain
    plane.cycle(), plane.cycle()  # z: seen end on from the front, so the drag's height moves it, up toward us
    before = plane.coordinate_m
    plane.drag(0.0, -2.0, camera)
    assert plane.coordinate_m == pytest.approx(before + 2 * 0.05)
