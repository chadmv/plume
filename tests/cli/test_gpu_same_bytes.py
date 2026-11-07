"""Two identical CUDA runs of the smoke puff preview write identical bytes.

The CPU same-bytes test (`test_run.py`) cannot catch nondeterminism that only the GPU has, such as
thread scheduling or atomics, so this runs the committed smoke puff preview twice on CUDA and compares
every output but `timing.txt` byte for byte. It skips on machines without a CUDA GPU, including CI.
"""

import shutil
from pathlib import Path

import pytest

from plume.cli.main import EXIT_OK, main
from plume.report.numbers import read_numbers

pytestmark = pytest.mark.gpu

REPO = Path(__file__).resolve().parents[2]
RECIPE = REPO / "recipes" / "smoke_puff.toml"


def run_preview_on_cuda(out: Path) -> Path:
    assert main(["run", str(RECIPE), "--preview", "--device", "cuda", "--out", str(out)]) == EXIT_OK
    return out / "preview"


def test_two_cuda_runs_write_identical_bytes(tmp_path, cuda_device):
    out = tmp_path / "out"
    preview = run_preview_on_cuda(out)
    first = tmp_path / "first"
    shutil.copytree(preview, first)
    shutil.rmtree(out)
    run_preview_on_cuda(out)

    summary, _ = read_numbers((preview / "numbers.txt").read_text())
    assert summary["backend"] == "cuda"
    names = sorted(path.name for path in first.iterdir() if path.name != "timing.txt")
    assert sorted(path.name for path in preview.iterdir() if path.name != "timing.txt") == names
    assert "smoke_puff.png" in names and "numbers.txt" in names
    for name in names:
        assert (first / name).read_bytes() == (preview / name).read_bytes(), name
