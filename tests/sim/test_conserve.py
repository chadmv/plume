import numpy as np
import pytest

from plume.recipe.schema import FaceSettings
from plume.sim.advect import advect_maccormack
from plume.sim.conserve import SmokeBudget
from support.grids import blob, fill, small_grid


def test_smoke_leaving_through_the_open_top_is_counted(cpu_device):
    # Smoke rising at 1 cell per step through an open top: each step loses the top layer's smoke.
    grid = small_grid(cpu_device, cells=(8, 8, 8), faces=FaceSettings(top="open", left="closed", right="closed",
                                                                       back="closed", front="closed"))
    fill(grid.smoke.data, np.ones(grid.cells))
    fill(grid.v.data, np.full(grid.v.data.shape, 0.5))  # 0.5 m/s, cell 0.1 m, dt 0.1 s: half a cell
    budget = SmokeBudget(grid)
    assert budget.expected_after(grid, 0.1) == pytest.approx(8 * 8 * 8 - 8 * 8 * 0.5)


def test_rescale_hits_the_target_and_keeps_the_shape(cpu_device):
    grid = small_grid(cpu_device)
    fill(grid.smoke.data, blob(grid.cells, (8, 8, 8), 2.0))
    fill(grid.u.data, np.full(grid.u.data.shape, 0.3))
    budget = SmokeBudget(grid)
    target = budget.expected_after(grid, 0.1)
    advect_maccormack(grid.smoke, tuple(f.data for f in grid.velocity_fields()), grid, 0.1)
    before = grid.smoke.next.numpy().copy()
    budget.rescale(grid, target)
    after = grid.smoke.next.numpy()
    assert after.astype(np.float64).sum() == pytest.approx(target, rel=1e-5)
    assert np.allclose(after, before * (after.sum() / before.sum()), rtol=1e-5)
