import numpy as np
import pytest

from plume.recipe.derived import derive
from plume.sim.run import simulate
from support.recipes import tiny_recipe

CLOSED = {"faces": {"bottom": "closed", "top": "closed", "left": "closed", "right": "closed",
                    "back": "closed", "front": "closed"}}


def run_and_collect(recipe, collect):
    results = []
    simulate(recipe, derive(recipe), "cpu", lambda frame, grid: results.append(collect(grid)))
    return results


def smoke_height(grid):
    smoke = grid.smoke.data.numpy()
    heights = np.arange(smoke.shape[1]) + 0.5
    return float((smoke.sum(axis=(0, 2)) * heights).sum() / smoke.sum())


def test_hot_puff_rises(cpu_device):
    recipe = tiny_recipe(emitter=[{"name": "puff", "center_m": [0.0, 0.25, 0.0], "radius_m": 0.15,
                                   "end_s": 0.2, "smoke_per_s": 5.0, "temperature_k": 600.0}],
                         time={"duration_s": 1.0, "frames": 4})
    heights = run_and_collect(recipe, smoke_height)
    assert heights == sorted(heights)
    assert heights[-1] - heights[0] > 2.0  # cells


def test_smoke_is_nearly_conserved_in_a_closed_box_without_dissipation(cpu_device):
    # Clamped MacCormack alone lost about 11 percent here over 40 steps; since slice 2 the smoke budget
    # (sim/conserve.py) rescales each step's total, so only float32 rounding is left.
    recipe = tiny_recipe(domain={"size_m": [1.2, 1.2, 1.2], "cell_m": 0.05, **CLOSED},
                         emitter=[{"name": "puff", "center_m": [0.0, 0.4, 0.0], "radius_m": 0.2,
                                   "end_s": 0.05, "smoke_per_s": 5.0, "temperature_k": 320.0}],
                         time={"duration_s": 2.0, "frames": 8, "substeps": 5})
    totals = run_and_collect(recipe, lambda grid: float(grid.smoke.data.numpy().sum()))
    assert totals[-1] == pytest.approx(totals[0], rel=1e-4)


def test_cooling_relaxes_temperature_toward_ambient(cpu_device):
    recipe = tiny_recipe(emitter=[{"name": "puff", "center_m": [0.0, 0.4, 0.0], "radius_m": 0.2,
                                   "end_s": 0.05, "temperature_k": 900.0}],
                         dissipation={"cooling_per_s": 3.0}, forces={"heat_buoyancy": 0.0})
    peaks = run_and_collect(recipe, lambda grid: float(grid.temperature.data.numpy().max()))
    assert peaks == sorted(peaks, reverse=True)
    assert peaks[-1] - 293.0 < 0.1 * (900.0 - 293.0)
