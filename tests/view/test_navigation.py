import math

import numpy as np
import pytest

from plume.render.camera import make_camera
from plume.view.navigation import (FIELD_OF_VIEW_DEG, FLY_RISE_S, PITCH_LIMIT_DEG, Navigation, smoke_bounds)

DOMAIN_MIN = (-1.0, 0.0, -1.0)
DOMAIN_SIZE = (2.0, 2.5, 2.0)


def navigation(perspective=False):
    nav = Navigation(DOMAIN_MIN, DOMAIN_SIZE)
    nav.set_viewport(800, 400)
    nav.home(20.0, 30.0, (0.1, 1.2), (1.0, 1.0))
    if perspective:
        nav.toggle_perspective()
    return nav


def test_home_is_the_sheet_camera_exactly():
    nav = navigation(perspective=True)
    nav.tumble(37.0, -12.0)
    nav.home(20.0, 30.0, (0.1, 1.2), (1.0, 1.0))
    sheet = make_camera(20.0, 30.0)
    right, up, toward = nav.basis()
    assert not nav.perspective
    assert np.array_equal(right, sheet.right) and np.array_equal(up, sheet.up)
    assert np.array_equal(toward, sheet.toward)
    camera = nav.view_camera()
    assert camera.top == pytest.approx(1.2 + 1.0)  # the rectangle fits: height decides at aspect 2
    assert camera.left == pytest.approx(0.1 - 2.0)


def test_tumble_turns_around_the_pivot_right_turns_the_scene_right_down_shows_the_top():
    nav = navigation()
    pivot, distance = nav.pivot.copy(), nav.distance
    eye_before = nav.eye()
    nav.tumble(50.0, 0.0)
    assert nav.yaw_deg < 30.0
    assert np.allclose(nav.pivot, pivot) and nav.distance == distance
    assert np.linalg.norm(nav.eye() - pivot) == pytest.approx(np.linalg.norm(eye_before - pivot))
    nav.tumble(0.0, 50.0)
    assert nav.pitch_deg > 20.0


def test_pitch_stops_at_88_degrees_either_side():
    nav = navigation()
    nav.tumble(0.0, 1e6)
    assert nav.pitch_deg == PITCH_LIMIT_DEG
    nav.look(0.0, -1e6)
    assert nav.pitch_deg == -PITCH_LIMIT_DEG


@pytest.mark.parametrize("perspective", [False, True])
def test_track_keeps_the_point_at_the_pivot_under_the_cursor(perspective):
    nav = navigation(perspective)
    pivot = nav.pivot.copy()
    x0, y0 = nav.view_camera().project(pivot)
    nav.track(10.0, -6.0)
    x1, y1 = nav.view_camera().project(pivot)
    assert (x1 - x0, y1 - y0) == pytest.approx((10.0, -6.0), abs=1e-6)


def test_dolly_and_wheel_move_in_toward_the_pivot():
    nav = navigation(perspective=True)
    distance = nav.distance
    nav.dolly(20.0, 0.0)
    assert nav.distance < distance
    nav.wheel(-2.0)
    assert nav.distance > distance * math.exp(-0.1)
    ortho = navigation()
    size = ortho.half_height
    ortho.dolly(0.0, 20.0)  # down is out
    assert ortho.half_height > size


def test_switching_projection_keeps_the_size_at_the_pivot():
    nav = navigation()
    size = nav.half_height
    nav.toggle_perspective()
    assert nav.distance * math.tan(math.radians(FIELD_OF_VIEW_DEG) / 2) == pytest.approx(size)
    nav.toggle_perspective()
    assert nav.half_height == pytest.approx(size)


def test_free_look_keeps_the_eye():
    nav = navigation(perspective=True)
    eye = nav.eye()
    nav.look(30.0, 15.0)
    assert np.allclose(nav.eye(), eye)
    assert nav.yaw_deg < 30.0 and nav.pitch_deg > 20.0


@pytest.mark.parametrize("keys, axis", [((1, 0, 0), "forward"), ((0, 1, 0), "right"), ((0, 0, 1), "up")])
def test_each_fly_key_moves_the_eye_along_its_axis(keys, axis):
    nav = navigation(perspective=True)
    right, _, toward = nav.basis()
    direction = {"forward": -toward, "right": right, "up": np.array([0.0, 1.0, 0.0])}[axis]
    eye = nav.eye()
    for _ in range(10):
        nav.fly(*keys, dt_s=0.01)
    moved = nav.eye() - eye
    assert np.allclose(moved / np.linalg.norm(moved), direction)


def test_fly_speed_eases_in_and_out_exactly():
    nav = navigation(perspective=True)
    speed = DOMAIN_SIZE[0]  # one domain width a second at trim 1
    nav.fly(1, 0, 0, dt_s=FLY_RISE_S)
    assert np.linalg.norm(nav.fly_velocity) == pytest.approx(speed * (1 - math.exp(-1)))
    for _ in range(100):
        nav.fly(1, 0, 0, dt_s=0.01)
    assert np.linalg.norm(nav.fly_velocity) == pytest.approx(speed)
    eye = nav.eye()
    for _ in range(200):
        nav.fly(0, 0, 0, dt_s=0.01)  # released: coasts to rest
    assert not nav.fly_velocity.any()
    coasted = np.linalg.norm(nav.eye() - eye)
    assert coasted == pytest.approx(speed * 0.035, rel=0.01)  # speed times the fall time constant
    nav.trim(1)
    assert nav.fly_trim == 1.25


def test_the_first_fly_key_switches_to_perspective():
    nav = navigation()
    nav.fly(0, 0, 0, dt_s=0.01)
    assert not nav.perspective
    nav.fly(1, 0, 0, dt_s=0.01)
    assert nav.perspective


def test_release_puts_the_pivot_on_the_hit_or_at_the_domain_centers_depth():
    nav = navigation(perspective=True)
    eye = nav.eye()
    _, _, toward = nav.basis()
    nav.release(eye - toward * 1.5)
    assert np.allclose(nav.eye(), eye) and nav.distance == pytest.approx(1.5)
    nav.release(None)
    assert np.allclose(nav.eye(), eye)
    assert nav.distance == pytest.approx((eye - nav.domain_center) @ toward)
    ortho = navigation()
    _, _, toward = ortho.basis()
    before, seen = ortho.pivot.copy(), ortho.view_camera()
    ortho.release(before - toward * 0.3)
    assert np.allclose(ortho.pivot, before - toward * 0.3)
    after = ortho.view_camera()
    assert (after.left, after.top) == pytest.approx((seen.left, seen.top))  # the picture does not move


def test_perspective_projection_hides_points_behind_the_eye():
    nav = navigation(perspective=True)
    camera = nav.view_camera()
    assert camera.project(nav.eye() + camera.toward) is None
    x, y = camera.project(nav.pivot)
    assert (x, y) == pytest.approx((400.0, 200.0))


def test_frame_fits_a_sphere_and_smoke_bounds_find_the_smoke():
    smoke = np.zeros((10, 10, 10))
    smoke[2:4, 5:6, 7:9] = 1.0
    center, radius = smoke_bounds(smoke, (0.0, 0.0, 0.0), 0.1, visible_density=0.5)
    assert center == pytest.approx([0.3, 0.55, 0.8])
    assert radius == pytest.approx(math.sqrt(0.2**2 + 0.1**2 + 0.2**2) / 2)
    assert smoke_bounds(smoke * 0.1, (0.0, 0.0, 0.0), 0.1, visible_density=0.5) is None
    nav = navigation()
    nav.frame(center, radius)
    assert np.array_equal(nav.pivot, center) and nav.half_height == pytest.approx(radius * 1.1)
