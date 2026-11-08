import numpy as np
import pytest

import dataclasses

from plume.recipe.schema import NORMAL_LAYOUT, SHADE_LAYOUT, BackgroundSettings, LookSettings
from plume.report.channels import channel_strip, strip_frame_indices
from plume.report.color import hex_to_linear
from plume.report.composite import SheetLook, composite
from plume.report.contact import contact_sheet
from plume.report.numbers import RunFacts, measure, numbers_text, peak_and_fade, read_numbers

LOOK = SheetLook(look=LookSettings(backgrounds=BackgroundSettings()), channels=NORMAL_LAYOUT,
                 light_dir=(-0.5, 0.7, 0.5))
SHADE_LOOK = dataclasses.replace(LOOK, channels=SHADE_LAYOUT)


def frame_with_square(thickness_byte, heat_byte=0, size=32, lo=8, hi=24):
    frame = np.zeros((size, size, 4), dtype=np.uint8)
    frame[..., 2:] = 128
    frame[lo:hi, lo:hi, 0] = heat_byte
    frame[lo:hi, lo:hi, 1] = thickness_byte
    return frame


def test_empty_pixels_composite_to_the_background_exactly():
    color = composite(frame_with_square(0), "#aac476", LOOK)
    assert np.allclose(color[0, 0], hex_to_linear("#aac476"))


def test_thick_smoke_hides_the_background():
    color = composite(frame_with_square(255), "#aac476", LOOK)
    assert not np.allclose(color[16, 16], hex_to_linear("#aac476"))


def shaded_square(shade_byte):
    frame = frame_with_square(255)
    frame[..., 2] = shade_byte
    frame[..., 3] = 255
    return frame


def test_shade_darkens_the_smoke_by_shade_depth():
    lit = composite(shaded_square(255), "#808080", SHADE_LOOK)[16, 16]
    shadowed = composite(shaded_square(0), "#808080", SHADE_LOOK)[16, 16]
    assert np.allclose(shadowed, lit * (1.0 - SHADE_LOOK.look.shade_depth))


def test_shade_depth_zero_ignores_the_shade():
    flat = dataclasses.replace(SHADE_LOOK, look=dataclasses.replace(SHADE_LOOK.look, shade_depth=0.0))
    assert np.allclose(composite(shaded_square(0), "#808080", flat), composite(shaded_square(255), "#808080", flat))


def test_measure_reports_coverage_box_and_means():
    rows = measure([frame_with_square(204, heat_byte=51)], fps=20.0)
    row = rows[0]
    assert row.time_s == pytest.approx(0.05)
    assert row.coverage == pytest.approx(0.25)
    assert row.box == pytest.approx((0.25, 0.25, 0.75, 0.75))
    assert row.mean_thick == pytest.approx(0.8)
    assert row.mean_heat == pytest.approx(0.2)
    assert row.total_thick == pytest.approx(256 * 0.8)


def test_peak_and_fade_frames():
    frames = [frame_with_square(b) for b in (50, 200, 150, 30, 10)]
    assert peak_and_fade(measure(frames, fps=10.0)) == (1, 4)
    assert peak_and_fade(measure(frames[:3], fps=10.0)) == (1, None)


def test_numbers_text_round_trips():
    frames = [frame_with_square(b) for b in (50, 200, 0)]
    facts = RunFacts(recipe="recipes/x.toml", backend="cpu", grid="8 x 8 x 8 cells of 0.100000 m", fps=10.0,
                     frame_m=1.5, heat_divisor=0.0, channels=SHADE_LAYOUT, shade_divisor=0.75)
    summary, rows = read_numbers(numbers_text(measure(frames, 10.0), facts))
    assert summary["channels"] == SHADE_LAYOUT
    assert summary["shade_divisor"] == "0.750000"
    normal = dataclasses.replace(facts, channels=NORMAL_LAYOUT, shade_divisor=None)
    assert "shade_divisor" not in read_numbers(numbers_text(measure(frames, 10.0), normal))[0]
    assert summary["peak_frame"] == "1"
    assert summary["fade_frame"] == "2"
    assert summary["grid"] == "8 x 8 x 8 cells of 0.100000 m"
    assert rows[2]["left"] == "-"
    assert float(rows[1]["mean_thick"]) == pytest.approx(200 / 255, abs=1e-4)


def test_strip_indices_are_evenly_spaced_from_first_to_last():
    assert strip_frame_indices(64) == [0, 13, 25, 38, 50, 63]
    assert strip_frame_indices(3) == [0, 1, 2]
    assert strip_frame_indices(1) == [0]


def test_contact_sheet_and_strip_sizes():
    frames = [frame_with_square(200)] * 5
    sheet = contact_sheet(frames, columns=3, background_hex="#808080", style=LOOK)
    assert sheet.size == (3 * 130 + 2, 2 * 130 + 2)
    strip = channel_strip(frames, LOOK)
    assert strip.size == (4 * 34 + 2, 18 + 5 * 34 + 2)
    assert channel_strip([shaded_square(128)] * 5, SHADE_LOOK).size == strip.size
