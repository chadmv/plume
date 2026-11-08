"""Assembling a shade layout sheet: A is unused, thin and empty pixels take their body's shade, and the
brightest well-covered smoke of the run maps to B = 255."""

import numpy as np
import pytest

from plume.recipe.schema import SHADE_LAYOUT, RenderSettings
from plume.render.camera import make_camera, make_domain_view
from plume.render.raw_frame import CHANNELS, SHADE, THICKNESS
from plume.sheet.assemble import assemble
from plume.sheet.crop import CropSquare
from plume.sheet.resample import resample_frame
from plume.sheet.shade import ease_thin_pixels, shade_divisor

VIEW = make_domain_view(make_camera(0.0, 0.0), (-1.0, 0.0, -1.0), (2.0, 2.0, 2.0), 0.0625, 2.0)  # 64 px
SETTINGS = RenderSettings()
SEAT = np.array([0.0, 1.0, 0.0])
BALL_RADIUS_PX = 12
HALO_RADIUS_PX = 18


def lit_ball(speckled_halo=False):
    """A raw frame (shade stored times thickness): a dense ball lit from the left (shade 0.9 on the left
    edge to 0.3 on the right), with, when asked, a thin halo whose shade is a checkerboard of 0.25 (the
    darkest the default fill allows) and 1: the speckle a few wisps of smoke give."""
    frame = np.zeros((64, 64, CHANNELS), dtype=np.float32)
    ys, xs = np.mgrid[0:64, 0:64] + 0.5
    distance = np.hypot(xs - 32, ys - 32)
    ball = distance < BALL_RADIUS_PX
    frame[ball, THICKNESS] = 0.9
    frame[ball, SHADE] = 0.9 * (0.9 - 0.6 * (xs[ball] - (32 - BALL_RADIUS_PX)) / (2 * BALL_RADIUS_PX))
    if speckled_halo:
        halo = (distance >= BALL_RADIUS_PX) & (distance < HALO_RADIUS_PX)
        checker = (np.floor(xs) + np.floor(ys)) % 2 == 0
        frame[halo, THICKNESS] = 0.02
        frame[halo, SHADE] = 0.02 * np.where(checker[halo], 0.25, 1.0)
    return frame


def test_every_alpha_byte_is_255():
    result = assemble([lit_ball(speckled_halo=True), lit_ball()], VIEW, SEAT, 64, SETTINGS, SHADE_LAYOUT)
    for frame in result.frames:
        assert np.all(frame[..., 3] == 255)


def test_empty_pixels_carry_their_neighborhood_shade():
    result = assemble([lit_ball()], VIEW, SEAT, 64, SETTINGS, SHADE_LAYOUT)
    frame = result.frames[0]
    empty = frame[..., 1] == 0
    assert empty.any()
    assert frame[empty, 2].min() > 0
    left_empty = empty & (np.arange(64)[None, :] < 32)
    right_empty = empty & (np.arange(64)[None, :] >= 32)
    assert frame[left_empty, 2].mean() > frame[right_empty, 2].mean()  # the lit side's edge stays lit


def test_a_speckled_thin_halo_is_smooth_and_no_darker_than_the_shaded_side():
    result = assemble([lit_ball(speckled_halo=True)], VIEW, SEAT, 64, SETTINGS, SHADE_LAYOUT)
    frame = result.frames[0]
    thickness = frame[..., 1].astype(np.float64) / 255.0
    shade = frame[..., 2].astype(np.float64)
    dense = thickness >= SETTINGS.shade_fade_thickness
    halo = (thickness > 0.0) & ~dense
    assert halo.any()
    # Measured: eased, the halo's darkest byte is 103 against the ball's darkest 91, and neighboring halo
    # bytes differ by at most 15; without easing they are 55 and 108 (a dark outline and the speckle).
    assert shade[halo].min() >= shade[dense].min() - 8
    neighbors = halo[:, 1:] & halo[:, :-1]
    assert np.abs(np.diff(shade, axis=1))[neighbors].max() <= 48


def test_the_brightest_well_covered_smoke_maps_to_255():
    result = assemble([lit_ball()], VIEW, SEAT, 64, SETTINGS, SHADE_LAYOUT)
    frame = result.frames[0]
    dense = frame[..., 1] >= SETTINGS.shade_fade_thickness * 255
    assert frame[dense, 2].max() == 255
    assert result.shade_divisor == pytest.approx(0.9, abs=0.05)


def test_easing_keeps_thick_pixels_and_fills_an_empty_frame_with_zero():
    frame = lit_ball()
    eased = ease_thin_pixels(frame, 0.1, 4.0)
    thick = frame[..., THICKNESS] >= 0.1
    assert np.allclose(eased[thick, SHADE], frame[thick, SHADE] / frame[thick, THICKNESS])
    empty = np.zeros_like(frame)
    assert not ease_thin_pixels(empty, 0.1, 4.0)[..., SHADE].any()


def test_divisor_falls_back_when_nothing_is_well_covered():
    thin = np.zeros((4, 4, CHANNELS))
    thin[1, 1, THICKNESS] = 0.01
    thin[1, 1, SHADE] = 0.5
    assert shade_divisor([thin], 0.1) == pytest.approx(0.5)  # shade_divisor reads eased (plain) shade
    assert shade_divisor([np.zeros((4, 4, CHANNELS))], 0.1) == 1.0


def test_resampling_keeps_shade_within_its_thickness():
    # Shrinking a hard-edged ball rings (bicubic); the weighted shade must stay between 0 and the thickness.
    frame = resample_frame(lit_ball(speckled_halo=True), CropSquare(left=3.3, top=2.7, side=57.0), 40,
                           SHADE_LAYOUT)
    assert np.all(frame[..., SHADE] >= 0.0)
    assert np.all(frame[..., SHADE] <= frame[..., THICKNESS])
