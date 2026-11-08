import itertools

import numpy as np
import pytest

from plume.recipe.derived import derive
from plume.recipe.schema import NORMAL_LAYOUT, SHADE_LAYOUT
from plume.render.raw_frame import CHANNELS, HEAT, NORMAL_X, NORMAL_Y, NORMAL_Z, SHADE, THICKNESS
from plume.report.color import to_srgb_bytes
from plume.report.composite import composite, decode, sheet_look
from plume.view.live_run import LiveRun
from plume.view.navigation import Navigation
from plume.view.viewport import (HEAT_VIEW, LOOK, SHADE_VIEW, THICKNESS_VIEW, LookTables, Viewport, look_inputs,
                                 shade_bytes)
from support.recipes import tiny_recipe

BYTES = np.arange(0, 256, 15, dtype=np.uint8)
HEAT_DIVISOR = 7.3
BACKGROUND = "#aac476"


def byte_grid(channels):
    """Every combination of heat, thickness and B (and A in the normal layout) bytes, as sheet pixels."""
    if channels == SHADE_LAYOUT:
        rows = [(h, g, b, 255) for h, g, b in itertools.product(BYTES, BYTES, BYTES)]
    else:
        rows = [(h, g, b, a) for h, g, b, a in itertools.product(BYTES, BYTES, BYTES, BYTES)
                if (b / 255 * 2 - 1) ** 2 + (a / 255 * 2 - 1) ** 2 <= 1.0]
    return np.array(rows, dtype=np.uint8)[None, :, :]  # one row of pixels


def raw_from_sheet_pixels(rgba, channels):
    """The raw march values those bytes stand for, at heat divisor HEAT_DIVISOR and shade divisor 1."""
    frame = decode(rgba, channels)
    raw = np.zeros((*rgba.shape[:2], CHANNELS), dtype=np.float64)
    raw[..., HEAT] = frame.heat * HEAT_DIVISOR
    raw[..., THICKNESS] = frame.thickness
    if channels == SHADE_LAYOUT:
        raw[..., SHADE] = frame.shade * frame.thickness
    else:
        raw[..., [NORMAL_X, NORMAL_Y, NORMAL_Z]] = frame.normal
    return raw


@pytest.mark.parametrize("channels", [SHADE_LAYOUT, NORMAL_LAYOUT])
def test_look_kernel_matches_report_composite(cpu_device, channels):
    recipe = tiny_recipe(output={"channels": channels})
    rgba = byte_grid(channels)
    raw = raw_from_sheet_pixels(rgba, channels)
    light = np.array(recipe.render.light_dir) / np.linalg.norm(recipe.render.light_dir)
    tables = LookTables(recipe, cpu_device)

    def viewer(view):
        inputs = look_inputs(recipe, view, HEAT_DIVISOR, 1.0, BACKGROUND, light)
        return shade_bytes(raw, recipe, tables, inputs, cpu_device).astype(int)

    expected = to_srgb_bytes(composite(rgba, BACKGROUND, sheet_look(recipe))).astype(int)
    assert np.abs(viewer(LOOK)[..., :3] - expected).max() <= 1
    assert np.all(viewer(LOOK)[..., 3] == 255)
    assert np.array_equal(viewer(HEAT_VIEW)[..., 0], rgba[..., 0])
    assert np.array_equal(viewer(THICKNESS_VIEW)[..., 1], rgba[..., 1])
    fourth = viewer(SHADE_VIEW)
    if channels == SHADE_LAYOUT:
        covered = rgba[..., 1] > 0  # the shade of an empty pixel is undefined; the viewer shows 0
        assert np.abs(fourth[..., 2][covered] - rgba[..., 2][covered]).max() <= 1
    else:
        assert np.abs(fourth[..., 0] - rgba[..., 2]).max() <= 1
        assert np.abs(fourth[..., 1] - rgba[..., 3]).max() <= 1


@pytest.fixture(scope="module")
def drawn(cpu_device):
    recipe = tiny_recipe(emitter=[{"name": "puff", "center_m": [0.0, 0.5, 0.0], "radius_m": 0.3, "end_s": 1.0,
                                   "smoke_per_s": 30.0}])
    derived = derive(recipe)
    run = LiveRun(recipe, derived, "cpu", budget_bytes=1e9)
    while run.advance() is not None:
        pass
    nav = Navigation(derived.domain_min_m, derived.size_m)
    nav.set_viewport(48, 40)
    nav.frame(np.array([0.0, 0.6, 0.0]), 0.9)
    viewport = Viewport(recipe, derived, "cpu")
    return recipe, run, nav, viewport


def test_a_drawn_puff_covers_the_middle_and_leaves_the_background_at_the_corners(drawn):
    recipe, run, nav, viewport = drawn
    for perspective in (False, True):
        if nav.perspective != perspective:
            nav.toggle_perspective()
        thickness = viewport.draw(run, 0, nav.view_camera(), THICKNESS_VIEW, BACKGROUND)
        look = viewport.draw(run, 0, nav.view_camera(), LOOK, BACKGROUND)
        assert thickness.shape == (40, 48, 4)
        assert thickness[20, 24, 1] > 100 and thickness[0, 0, 1] == 0
        assert np.array_equal(look[0, 0, :3], to_srgb_bytes(composite(np.zeros((1, 1, 4), np.uint8), BACKGROUND,
                                                                      sheet_look(recipe)))[0, 0])
    half = viewport.draw(run, 0, nav.view_camera(24, 20), THICKNESS_VIEW, BACKGROUND)
    assert half.shape == (20, 24, 4) and half[10, 12, 1] > 100


def test_the_center_ray_finds_the_puffs_near_side(drawn):
    _, run, nav, viewport = drawn
    if not nav.perspective:
        nav.toggle_perspective()
    camera = nav.view_camera()
    hit = viewport.center_hit(run, 0, camera)
    assert hit is not None
    ahead = camera.ahead(hit)
    assert 0.0 < ahead < camera.ahead(np.array([0.0, 0.6, 0.0]))  # in front of the puff's middle
    away = nav.view_camera()
    empty = viewport.center_hit(run, 0, type(away)(**{**away.__dict__, "toward": -away.toward}))
    assert empty is None
