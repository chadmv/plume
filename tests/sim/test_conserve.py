import numpy as np
import pytest

from plume.recipe.derived import derive
from plume.sim.conserve import held_total
from plume.sim.reduce import TripleSum
from plume.sim.run import simulate
from support.recipes import tiny_recipe


def test_held_total_never_gains_and_never_drops_below_semi_lagrangian():
    assert held_total(before=10.0, semi_lagrangian=9.0, maccormack=12.0) == 10.0  # a gain is removed
    assert held_total(before=10.0, semi_lagrangian=9.0, maccormack=9.5) == 9.5  # in bounds: unchanged
    assert held_total(before=10.0, semi_lagrangian=9.0, maccormack=8.0) == 9.0  # never below the plain pass
    assert held_total(before=10.0, semi_lagrangian=4.0, maccormack=3.0) == 4.0  # outflow counts as the scheme does


def test_triple_sum_matches_numpy(cpu_device):
    import warp as wp

    rng = np.random.default_rng(2)
    arrays = [rng.random((5, 7, 9)).astype(np.float32) for _ in range(3)]
    sums = TripleSum((5, 7, 9), "cpu")(*(wp.array(a, device="cpu") for a in arrays))
    assert sums == pytest.approx([a.astype(np.float64).sum() for a in arrays], rel=1e-6)


def smoke_below(height_m, recipe):
    totals = []

    def capture(frame, grid):
        smoke = grid.smoke.data.numpy().astype(np.float64)
        rows = int(round(height_m / recipe.domain.cell_m))
        totals.append(smoke[:, :rows, :].sum())

    simulate(recipe, derive(recipe), "cpu", capture)
    return totals


def test_an_open_top_does_not_drain_smoke_still_inside(cpu_device):
    # The review's probe: a hot puff in a 0.8 m domain with an open top against the same puff in a 2.4 m
    # domain, counting smoke below 0.8 m. Smoke inside must not fade faster because some left. The first
    # budget (before minus estimated outflow) left 0.16 against 7.3 by frame 2.
    puff = [{"name": "puff", "center_m": [0.0, 0.3, 0.0], "radius_m": 0.2, "end_s": 0.1, "smoke_per_s": 20.0,
             "temperature_k": 900.0}]
    short = smoke_below(0.8, tiny_recipe(domain={"size_m": [1.2, 0.8, 1.2], "cell_m": 0.05}, emitter=puff))
    tall = smoke_below(0.8, tiny_recipe(domain={"size_m": [1.2, 2.4, 1.2], "cell_m": 0.05}, emitter=puff))
    for frame, (s, t) in enumerate(zip(short, tall)):
        assert s > 0.8 * t, frame  # measured 1.0 to 1.3 (the open top changes the flow a little)
