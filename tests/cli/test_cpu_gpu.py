import numpy as np
import pytest
from PIL import Image

from plume.cli.main import EXIT_OK, main
from plume.report.numbers import read_numbers

from support.tiny import TINY

pytestmark = pytest.mark.gpu


def run_on(tmp_path, device):
    recipe = tmp_path / "tiny.toml"
    recipe.write_text(TINY)
    out = tmp_path / device
    assert main(["run", str(recipe), "--device", device, "--out", str(out)]) == EXIT_OK
    return out


def test_cpu_and_gpu_agree_within_tolerance(tmp_path, cuda_device):
    cpu = run_on(tmp_path, "cpu")
    gpu = run_on(tmp_path, "cuda")
    cpu_sheet = np.asarray(Image.open(cpu / "tiny.png")).astype(int)
    gpu_sheet = np.asarray(Image.open(gpu / "tiny.png")).astype(int)
    assert cpu_sheet.shape == gpu_sheet.shape
    assert np.abs(cpu_sheet[..., 1] - gpu_sheet[..., 1]).max() <= 3
    assert np.abs(cpu_sheet[..., 2:] - gpu_sheet[..., 2:]).max() <= 6
    _, cpu_rows = read_numbers((cpu / "numbers.txt").read_text())
    _, gpu_rows = read_numbers((gpu / "numbers.txt").read_text())
    for cpu_row, gpu_row in zip(cpu_rows, gpu_rows):
        for key in ("coverage", "mean_thick", "total_thick"):
            assert float(gpu_row[key]) == pytest.approx(float(cpu_row[key]), rel=0.02), key
