import numpy as np
import pytest

from plume.sim.pressure import compute_divergence
from plume.sim.turbulence import apply_turbulence
from support.grids import small_grid


def pushed(cpu_device, seed=1, time_s=0.0, cells=(16, 16, 16), cell_m=0.1, scale_m=0.4, speed_mps=0.2):
    """The velocity one unit step of turbulence gives a grid at rest."""
    grid = small_grid(cpu_device, cells=cells, cell_m=cell_m)
    apply_turbulence(grid, seed, scale_m, 1.0, speed_mps, time_s, 1.0)
    return grid


def faces(grid):
    return [field.data.numpy().copy() for field in grid.velocity_fields()]


def test_zero_strength_changes_nothing(cpu_device):
    grid = small_grid(cpu_device)
    apply_turbulence(grid, 1, 0.4, 0.0, 0.2, 0.0, 1.0)
    assert all(not f.any() for f in faces(grid))


def test_the_push_neither_squeezes_nor_spreads_the_gas(cpu_device):
    grid = pushed(cpu_device)
    magnitude = max(np.abs(f).max() for f in faces(grid))
    divergence = np.abs(compute_divergence(grid).numpy()).max() * grid.info.cell_m
    # Measured: peak push 3.4 per unit strength, divergence 1.2e-7 of it (float rounding).
    assert magnitude > 0.3
    assert divergence < 1e-5 * magnitude


def test_same_seed_repeats_and_another_seed_differs(cpu_device):
    first, again, other = faces(pushed(cpu_device, 1)), faces(pushed(cpu_device, 1)), faces(pushed(cpu_device, 2))
    assert all(np.array_equal(a, b) for a, b in zip(first, again))
    assert not all(np.array_equal(a, b) for a, b in zip(first, other))


def correlation(a, b):
    a = np.concatenate([f.ravel() for f in a])
    b = np.concatenate([f.ravel() for f in b])
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_the_pattern_changes_over_its_renewal_time(cpu_device):
    # Renewal time is scale_m / speed_mps = 2 s here. Measured correlations: 0.999999 and 0.02.
    start = faces(pushed(cpu_device, time_s=0.0))
    assert correlation(start, faces(pushed(cpu_device, time_s=0.05))) > 0.99
    assert correlation(start, faces(pushed(cpu_device, time_s=2.0))) < 0.5


def test_preview_and_final_cell_sizes_give_the_same_push(cpu_device):
    # The same 1.6 m box at 0.05 m and 0.1 m cells: the push at matching faces agrees (D30).
    fine = pushed(cpu_device, cells=(32, 32, 32), cell_m=0.05, scale_m=0.5).v.data.numpy()
    coarse = pushed(cpu_device, cells=(16, 16, 16), cell_m=0.1, scale_m=0.5).v.data.numpy()
    # Coarse face (i, j, k) sits where fine face (2i + 0.5, 2j, 2k + 0.5) does; average the fine
    # neighbors in x and z to land on it.
    matched = 0.25 * (fine[0::2, 0::2, 0::2] + fine[1::2, 0::2, 0::2] + fine[0::2, 0::2, 1::2]
                      + fine[1::2, 0::2, 1::2])
    error = np.abs(matched - coarse).max() / np.abs(coarse).max()
    assert error < 0.05  # measured 0.008
