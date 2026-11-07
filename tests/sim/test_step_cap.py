import math

import numpy as np
import pytest

from plume.recipe.derived import derive
from plume.recipe.errors import RecipeError
from plume.sim.run import simulate
from support.recipes import tiny_recipe


def run(recipe):
    smoke = []
    log = simulate(recipe, derive(recipe), "cpu", lambda frame, grid: smoke.append(grid.smoke.data.numpy().copy()))
    return log, smoke


def test_a_slow_puff_keeps_its_substeps(cpu_device):
    recipe = tiny_recipe()
    log, _ = run(recipe)
    assert log.steps_per_frame == (3, 3, 3, 3)
    assert log.added_steps == 0


def test_a_cap_that_never_binds_changes_nothing(cpu_device):
    # Against slice 1's loop, which stepped at `step count * dt` with no cap: identical bytes.
    from plume.sim.grid import make_grid
    from plume.sim.stepper import Stepper

    recipe = tiny_recipe()
    derived = derive(recipe)
    _, capped = run(recipe)
    grid = make_grid(derived, recipe.domain.cell_m, recipe.domain.faces, recipe.domain.ambient_k, "cpu")
    stepper = Stepper(grid, recipe)
    uncapped = []
    for frame in range(recipe.time.frames):
        for index in range(derived.steps_per_frame):
            stepper.step((frame * derived.steps_per_frame + index) * derived.dt_s, derived.dt_s)
        uncapped.append(grid.smoke.data.numpy().copy())
    assert all(np.array_equal(a, b) for a, b in zip(capped, uncapped))


def test_a_fast_emitter_gets_more_steps(cpu_device):
    # 4 frames over 1 s with 3 substeps: blocks of 0.25 s. An emitter at 4 m/s in 0.05 m cells must cross
    # at most 1 cell per step: ceil(4 * 0.25 / 0.05) = 20 steps in frame 0. In frame 1 the projection has
    # sped some faces past 4 m/s (measured: 23 steps).
    recipe = tiny_recipe(emitter=[{"name": "jet", "center_m": [0.0, 0.3, 0.0], "radius_m": 0.15,
                                   "end_s": 0.5, "smoke_per_s": 5.0, "velocity_mps": [0.0, 4.0, 0.0]}])
    log, _ = run(recipe)
    assert log.steps_per_frame[0] == 20
    assert log.steps_per_frame[1] >= 20
    assert all(steps >= 3 for steps in log.steps_per_frame)
    assert log.added_steps > 0


def test_more_than_max_substeps_is_an_error(cpu_device):
    recipe = tiny_recipe(emitter=[{"name": "jet", "center_m": [0.0, 0.3, 0.0], "radius_m": 0.15,
                                   "end_s": 0.5, "velocity_mps": [0.0, 4.0, 0.0]}],
                         solver={"max_substeps": 10})
    with pytest.raises(RecipeError, match="max_substeps"):
        run(recipe)


def test_two_runs_choose_the_same_steps(cpu_device):
    recipe = tiny_recipe(emitter=[{"name": "jet", "center_m": [0.0, 0.3, 0.0], "radius_m": 0.15,
                                   "end_s": 0.5, "smoke_per_s": 5.0, "velocity_mps": [0.0, 2.0, 0.0]}])
    assert run(recipe)[0] == run(recipe)[0]


def test_warmup_runs_in_blocks(cpu_device, monkeypatch):
    # Warmup 0.6 s at dt 1/12 s is 7 base steps: blocks of 3, 3 and 1.
    from plume.sim import step_cap

    blocks = []
    original = step_cap.StepCap.plan

    def recording_plan(self, grid, start_s, length_s, base_steps, label):
        blocks.append((label, base_steps))
        return original(self, grid, start_s, length_s, base_steps, label)

    monkeypatch.setattr(step_cap.StepCap, "plan", recording_plan)
    log, _ = run(tiny_recipe(time={"duration_s": 1.0, "frames": 4, "warmup_s": 0.6}))
    assert [base for label, base in blocks if label == "warmup"] == [3, 3, 1]
    assert log.warmup_steps == 7
    assert math.isclose(log.total_steps, 7 + 12)
