import math

import numpy as np
import pytest

from plume.recipe.errors import RecipeError
from plume.sim.forces import apply_drag
from plume.sim.vorticity import VorticityConfinement
from support.grids import fill, small_grid
from support.recipes import tiny_recipe


def set_uniform(grid, velocity):
    for value, field in zip(velocity, grid.velocity_fields()):
        fill(field.data, np.full(field.data.shape, value))


def test_drag_without_wind_decays_velocity_exponentially(cpu_device):
    grid = small_grid(cpu_device)
    set_uniform(grid, (1.0, -2.0, 0.5))
    for _ in range(10):
        apply_drag(grid, (0.0, 0.0, 0.0), 2.0, 0.05)
    expected = math.exp(-2.0 * 0.5)
    assert grid.u.data.numpy() == pytest.approx(1.0 * expected, rel=1e-5)
    assert grid.v.data.numpy() == pytest.approx(-2.0 * expected, rel=1e-5)


def test_drag_pulls_the_gas_toward_the_wind(cpu_device):
    grid = small_grid(cpu_device)
    for _ in range(100):
        apply_drag(grid, (1.5, 0.0, -0.5), 4.0, 0.05)
    assert grid.u.data.numpy() == pytest.approx(1.5, abs=1e-4)
    assert grid.w.data.numpy() == pytest.approx(-0.5, abs=1e-4)


def test_wind_without_drag_is_a_recipe_error():
    with pytest.raises(RecipeError, match="drag_per_s"):
        tiny_recipe(forces={"wind_mps": [1.0, 0.0, 0.0]})


def vortex_tube(grid, sigma=0.25):
    """A swirl around a z-aligned line through the grid's center, counterclockwise seen from +z, with a
    core `sigma` meters wide."""
    nx, ny, nz = grid.cells
    cell = grid.info.cell_m

    def swirl(shape, offset, component):
        idx = np.indices(shape).astype(np.float64)
        x = (idx[0] + offset[0]) * cell - nx * cell / 2
        y = (idx[1] + offset[1]) * cell - ny * cell / 2
        falloff = np.exp(-(x**2 + y**2) / (2 * sigma**2))
        return -y * falloff / sigma if component == 0 else x * falloff / sigma

    fill(grid.u.data, swirl(grid.u.data.shape, (0.0, 0.5), 0))
    fill(grid.v.data, swirl(grid.v.data.shape, (0.5, 0.0), 1))


def peak_spin(grid):
    curl = VorticityConfinement(grid).measure_curl(grid).numpy()
    return float(np.linalg.norm(curl, axis=-1).max())


def test_confinement_at_zero_changes_nothing(cpu_device):
    grid = small_grid(cpu_device)
    vortex_tube(grid)
    before = [field.data.numpy().copy() for field in grid.velocity_fields()]
    VorticityConfinement(grid).apply(grid, 0.0, 0.05)
    for old, field in zip(before, grid.velocity_fields()):
        assert np.array_equal(old, field.data.numpy())


def test_confinement_spins_a_vortex_faster(cpu_device):
    grid = small_grid(cpu_device)
    vortex_tube(grid)
    before = peak_spin(grid)
    confinement = VorticityConfinement(grid)
    for _ in range(10):
        confinement.apply(grid, 5.0, 0.02)
    assert peak_spin(grid) > 1.5 * before  # measured 2.5 times


def test_confinement_push_grows_with_cell_size(cpu_device):
    # The same swirl in meters on a 32-cell and a 16-cell grid of the same domain: the push near the core
    # about doubles with the cell size (D30). Measured ratio 1.75: the coarse grid resolves the core less
    # well, so its spin and spin gradient are a little lower.
    pushes = []
    for cells, cell_m in (((32, 32, 4), 0.05), ((16, 16, 2), 0.1)):
        grid = small_grid(cpu_device, cells=cells, cell_m=cell_m)
        vortex_tube(grid)
        confinement = VorticityConfinement(grid)
        confinement.measure_curl(grid)
        confinement.apply(grid, 1.0, 0.0)
        pushes.append(float(np.linalg.norm(confinement.push.numpy(), axis=-1).max()))
    assert 1.5 < pushes[1] / pushes[0] < 2.2
