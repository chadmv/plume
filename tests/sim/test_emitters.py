import math

import numpy as np
import pytest

from plume.sim.emitters import emit, emitter_params
from support.grids import small_grid
from support.recipes import tiny_recipe

CELL_M = 0.05


def emitted_grid(device, seed=1, time_s=0.0, steps=1, dt=0.05, **emitter):
    settings = {"name": "e", "center_m": [0.0, 0.6, 0.0], "radius_m": 0.3, "end_s": 1.0, "smoke_per_s": 2.0}
    settings.update(emitter)
    recipe = tiny_recipe(seed=seed, emitter=[settings])
    grid = small_grid(device, cells=(24, 24, 24), cell_m=CELL_M)
    params = emitter_params(recipe.emitter, device)
    for step in range(steps):
        emit(grid, params, recipe.seed, time_s + step * dt, dt)
    return grid


def test_sphere_emits_rate_times_volume(cpu_device):
    grid = emitted_grid(cpu_device, steps=20, edge_softness=0.0)
    total = grid.smoke.data.numpy().sum() * CELL_M**3
    assert total == pytest.approx(2.0 * 4.0 / 3.0 * math.pi * 0.3**3, rel=0.05)


def test_nothing_is_emitted_outside_the_active_window(cpu_device):
    grid = emitted_grid(cpu_device, time_s=1.0)
    assert grid.smoke.data.numpy().sum() == 0.0


def test_temperature_is_held_inside_the_emitter(cpu_device):
    grid = emitted_grid(cpu_device, temperature_k=900.0, edge_softness=0.0)
    temperature = grid.temperature.data.numpy()
    assert temperature[12, 12, 12] == pytest.approx(900.0)
    assert temperature[0, 0, 0] == pytest.approx(293.0)


def test_same_seed_gives_identical_noise_and_another_seed_differs(cpu_device):
    noisy = {"noise": {"scale_m": 0.1, "strength": 0.8}}
    first = emitted_grid(cpu_device, seed=7, **noisy).smoke.data.numpy()
    again = emitted_grid(cpu_device, seed=7, **noisy).smoke.data.numpy()
    other = emitted_grid(cpu_device, seed=8, **noisy).smoke.data.numpy()
    assert np.array_equal(first, again)
    assert not np.array_equal(first, other)


def test_outward_velocity_points_away_from_the_center(cpu_device):
    grid = emitted_grid(cpu_device, velocity_mps=[0.0, 2.0, 0.0], velocity_mode="outward", edge_softness=0.0)
    u = grid.u.data.numpy()
    assert u[16, 12, 12] > 1.9  # right of center, pointing right
    assert u[8, 12, 12] < -1.9  # left of center, pointing left
