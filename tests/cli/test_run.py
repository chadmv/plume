import json
import shutil
import tomllib

import numpy as np
import pytest
from PIL import Image

from plume.cli.main import EXIT_OK, main
from plume.recipe.schema import NORMAL_LAYOUT, SHADE_LAYOUT
from plume.report.numbers import read_numbers
from support.tiny import TINY


OUTPUTS = ("tiny.png", "tiny.json", "contact_neutral.png", "contact_grass.png", "channels.png", "numbers.txt",
           "settings.toml", "timing.txt")


def run_tiny(tmp_path, out_name="out", channels=None):
    recipe = tmp_path / "tiny.toml"
    recipe.write_text(TINY if channels is None else TINY + f'channels = "{channels}"\n')
    out = tmp_path / out_name
    assert main(["run", str(recipe), "--device", "cpu", "--out", str(out)]) == EXIT_OK
    return out


def test_run_writes_every_output(tmp_path, capsys):
    out = run_tiny(tmp_path)
    for name in OUTPUTS:
        assert (out / name).is_file(), name
    sheet = json.loads((out / "tiny.json").read_text())
    assert sheet["frames"] == 4 and sheet["columns"] == 2 and sheet["frame_px"] == 64
    assert sheet["fps"] == 4.0
    assert sheet["written_by"].startswith("plume run ")
    summary, rows = read_numbers((out / "numbers.txt").read_text())
    assert summary["backend"] == "cpu"
    assert len(rows) == 4
    out_text = capsys.readouterr().out
    assert "peak_frame" in out_text
    assert "added by the CFL cap" in out_text
    resolved = tomllib.loads((out / "settings.toml").read_text())["resolved"]
    assert len(resolved["steps_per_frame"]) == 4 and min(resolved["steps_per_frame"]) >= 3
    assert resolved["total_steps"] == sum(resolved["steps_per_frame"])


def test_the_default_sheet_holds_shade_with_alpha_255(tmp_path):
    out = run_tiny(tmp_path)
    assert json.loads((out / "tiny.json").read_text())["channels"] == SHADE_LAYOUT
    sheet = np.asarray(Image.open(out / "tiny.png"))
    assert np.all(sheet[..., 3] == 255)
    covered = sheet[..., 1] >= 128
    assert covered.any() and sheet[covered, 2].max() > 0
    assert read_numbers((out / "numbers.txt").read_text())[0]["channels"] == SHADE_LAYOUT


def test_the_normal_layout_writes_normals(tmp_path):
    out = run_tiny(tmp_path, channels=NORMAL_LAYOUT)
    assert json.loads((out / "tiny.json").read_text())["channels"] == NORMAL_LAYOUT
    sheet = np.asarray(Image.open(out / "tiny.png"))
    empty = (sheet[..., 0] == 0) & (sheet[..., 1] == 0)
    assert np.all(sheet[empty, 2:] == 128)
    assert "shade_divisor" not in read_numbers((out / "numbers.txt").read_text())[0]


@pytest.mark.parametrize("channels", [SHADE_LAYOUT, NORMAL_LAYOUT])
def test_identical_runs_write_identical_bytes(tmp_path, channels):
    out = run_tiny(tmp_path, channels=channels)
    first = tmp_path / "first"
    shutil.copytree(out, first)
    run_tiny(tmp_path, channels=channels)
    for name in OUTPUTS:
        if name != "timing.txt":
            assert (first / name).read_bytes() == (out / name).read_bytes(), name


def test_preview_writes_into_a_preview_folder(tmp_path):
    recipe = tmp_path / "tiny.toml"
    recipe.write_text(TINY)
    assert main(["run", str(recipe), "--preview", "--device", "cpu", "--out", str(tmp_path / "o")]) == EXIT_OK
    sheet = json.loads((tmp_path / "o" / "preview" / "tiny.json").read_text())
    assert sheet["frames"] == 16 and sheet["frame_px"] == 128
