import numpy as np
import pytest

from support.grids import blob, fill, small_grid
from plume.sim.advect import advect_maccormack, advect_semi_lagrangian


def velocity(grid):
    return tuple(f.data for f in grid.velocity_fields())


def swirl(grid):
    nx, ny, nz = grid.cells
    x = np.arange(nx + 1)[:, None, None] / nx
    y = np.arange(ny)[None, :, None] / ny
    fill(grid.u.data, np.broadcast_to(np.sin(np.pi * x) * np.cos(np.pi * (y + 0.5 / ny)), (nx + 1, ny, nz)))
    xv = np.arange(nx)[:, None, None] / nx
    yv = np.arange(ny + 1)[None, :, None] / ny
    fill(grid.v.data, np.broadcast_to(-np.cos(np.pi * (xv + 0.5 / nx)) * np.sin(np.pi * yv), (nx, ny + 1, nz)))


def center_of_mass_x(values):
    xs = np.arange(values.shape[0]) + 0.5
    return float((values.sum(axis=(1, 2)) * xs).sum() / values.sum())


def test_constant_field_stays_constant(cpu_device):
    grid = small_grid(cpu_device)
    swirl(grid)
    fill(grid.smoke.data, np.ones(grid.cells))
    for _ in range(5):
        advect_maccormack(grid.smoke, velocity(grid), grid, dt=0.05)
        grid.smoke.swap()
    assert np.allclose(grid.smoke.data.numpy(), 1.0, atol=1e-5)


def test_blob_moves_with_uniform_flow(cpu_device):
    grid = small_grid(cpu_device, cells=(32, 12, 12))
    fill(grid.u.data, np.full(grid.u.data.shape, 1.0))  # 1 m/s = 10 cells/s
    fill(grid.smoke.data, blob(grid.cells, (8.0, 6.0, 6.0), 2.0))
    start = center_of_mass_x(grid.smoke.data.numpy())
    for _ in range(20):
        advect_maccormack(grid.smoke, velocity(grid), grid, dt=0.05)
        grid.smoke.swap()
    assert center_of_mass_x(grid.smoke.data.numpy()) - start == pytest.approx(10.0, abs=0.5)


def test_maccormack_keeps_peaks_sharper_than_semi_lagrangian(cpu_device):
    peaks = {}
    for name, advect in (("sl", advect_semi_lagrangian), ("mc", advect_maccormack)):
        grid = small_grid(cpu_device, cells=(32, 12, 12))
        fill(grid.u.data, np.full(grid.u.data.shape, 0.37))
        fill(grid.smoke.data, blob(grid.cells, (8.0, 6.0, 6.0), 1.5))
        for _ in range(20):
            advect(grid.smoke, velocity(grid), grid, dt=0.05)
            grid.smoke.swap()
        peaks[name] = grid.smoke.data.numpy().max()
    assert peaks["mc"] > peaks["sl"] * 1.1


def test_clamping_never_creates_new_extremes(cpu_device):
    grid = small_grid(cpu_device)
    swirl(grid)
    rng = np.random.default_rng(3)
    start = rng.random(grid.cells)
    fill(grid.smoke.data, start)
    advect_maccormack(grid.smoke, velocity(grid), grid, dt=0.1)
    grid.smoke.swap()
    result = grid.smoke.data.numpy()
    assert result.min() >= start.min() - 1e-6
    assert result.max() <= start.max() + 1e-6
