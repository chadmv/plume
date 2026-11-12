"""The numbers strip's data: the series are `measure`'s numbers of the sheet, and the marks."""

import numpy as np

from plume.report.numbers import measure
from plume.view.numbers_strip import capped_frames, frame_tooltip, strip_data


def sheet_frames():
    frames = []
    for index in range(3):
        frame = np.zeros((16, 16, 4), dtype=np.uint8)
        frame[4:4 + 3 * index, 4:10, 1] = 200
        frame[5, 5, 0] = 60 * index
        frames.append(frame)
    return frames


def test_the_series_are_the_sheets_numbers():
    frames = sheet_frames()
    data = strip_data(3, frames, 24.0)
    rows = measure(frames, 24.0)
    assert np.array_equal(data.series["coverage"], [row.coverage for row in rows])
    assert np.array_equal(data.series["mean thickness"], [row.mean_thick for row in rows])
    assert np.array_equal(data.series["peak heat"], [row.peak_heat for row in rows])


def test_before_the_sheet_there_are_no_series_but_the_marks_show():
    data = strip_data(4, None, 24.0, {0: (), 2: ("top",), 3: ("top", "front")}, (3, 3, 5, 3), 3)
    assert data.series == {}
    assert data.edges == {2: ("top",), 3: ("top", "front")}
    assert data.capped == (2,)
    assert "smoke reaches top, front" in frame_tooltip(data, 3)
    assert "step cap" in frame_tooltip(data, 2)


def test_capped_frames_are_those_over_the_base():
    assert capped_frames(None, 3) == ()
    assert capped_frames((3, 4, 3, 6), 3) == (1, 3)
