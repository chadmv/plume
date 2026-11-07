"""The smoke puff preview, rerun on CPU, matches the numbers of the approved run within tolerance.

`tests/golden/smoke_puff_preview.numbers.txt` is the `numbers.txt` of the approved preview look. It was
first taken on CUDA at the end of slice 1, then retaken on CPU when the preview began keeping the full
run's step length. When a change is meant to alter the look, get the new look
approved, then copy the new preview's `numbers.txt` over the golden file.
"""

from pathlib import Path

import pytest

from plume.cli.main import EXIT_OK, main
from plume.report.numbers import read_numbers

REPO = Path(__file__).resolve().parents[2]
RECIPE = REPO / "recipes" / "smoke_puff.toml"
GOLDEN = REPO / "tests" / "golden" / "smoke_puff_preview.numbers.txt"

SAME_SUMMARY_KEYS = ("recipe", "grid", "frames")
CLOSE_SUMMARY_KEYS = ("fps", "frame_m")
FRAME_KEYS = ("peak_frame", "fade_frame")
BOX_KEYS = ("left", "top", "right", "bottom")
AMOUNT_KEYS = ("coverage", "mean_thick", "total_thick")
HEAT_KEYS = ("mean_heat", "peak_heat")

RELATIVE = 0.02  # amounts within 2 percent
AMOUNT_FLOOR = 1e-3  # amounts this close count as equal however small they are
BOX_FRACTION = 0.02  # box edges within about 2 px of a 128 px preview frame
HEAT_FRACTION = 0.02  # heat values are already fractions of the hottest frame
FRAME_SLACK = 1  # peak and fade frames may move by one frame


def test_smoke_puff_preview_matches_golden_numbers(tmp_path):
    assert main(["run", str(RECIPE), "--preview", "--device", "cpu", "--out", str(tmp_path)]) == EXIT_OK
    actual_summary, actual_rows = read_numbers((tmp_path / "preview" / "numbers.txt").read_text())
    golden_summary, golden_rows = read_numbers(GOLDEN.read_text())
    assert_summaries_close(actual_summary, golden_summary)
    assert len(actual_rows) == len(golden_rows)
    for actual, golden in zip(actual_rows, golden_rows):
        assert_rows_close(actual, golden)


def assert_summaries_close(actual: dict[str, str], golden: dict[str, str]) -> None:
    for key in SAME_SUMMARY_KEYS:
        assert actual[key] == golden[key], key
    for key in CLOSE_SUMMARY_KEYS:
        assert float(actual[key]) == pytest.approx(float(golden[key]), rel=1e-6), key
    for key in FRAME_KEYS:
        assert (actual[key] == "never") == (golden[key] == "never"), key
        if golden[key] != "never":
            assert abs(int(actual[key]) - int(golden[key])) <= FRAME_SLACK, key


def assert_rows_close(actual: dict[str, str], golden: dict[str, str]) -> None:
    where = f"frame {golden['frame']}"
    assert actual["frame"] == golden["frame"]
    assert float(actual["time_s"]) == pytest.approx(float(golden["time_s"])), where
    for key in BOX_KEYS:
        assert (actual[key] == "-") == (golden[key] == "-"), f"{where} {key}"
        if golden[key] != "-":
            assert float(actual[key]) == pytest.approx(float(golden[key]), abs=BOX_FRACTION), f"{where} {key}"
    for key in AMOUNT_KEYS:
        assert float(actual[key]) == pytest.approx(float(golden[key]), rel=RELATIVE, abs=AMOUNT_FLOOR), \
            f"{where} {key}"
    for key in HEAT_KEYS:
        assert float(actual[key]) == pytest.approx(float(golden[key]), abs=HEAT_FRACTION), f"{where} {key}"
