"""Multigrid pressure. Bounds come from probes run while building T2.2 (CPU, Warp 1.19.0):

- A smooth upward jet (a Gaussian blob of v, radius a fifth of the short axis) is what Gauss-Seidel handles
  worst. Relative Poisson residual after each single V-cycle with 2 sweeps a side:
  64 cubed closed 0.11, 0.011, 0.001; open 0.86, 0.16, 0.029; 80 x 100 x 80 closed 0.12, 0.012, 0.002;
  open 0.93, 0.21, 0.039. Before coarse levels weighed their overhanging cells, 80 x 100 x 80 closed
  converged only 0.78 per cycle.
- 60 Gauss-Seidel sweeps leave that jet's divergence at 0.27 to 1.04 of where it started at about 32
  cubed and 1.9 to 2.0 at 80 x 100 x 80; 2 V-cycles leave 0.010 to 0.054 and 0.012 (closed) to 0.21
  (open). On 16 cubed with
  open faces Gauss-Seidel is better (0.001 against 0.015): the grid is too small for long waves.
- Tall, thin domains stop coarsening at 2 cells across while still long (6 x 128 x 6 ends at 2 x 32 x 2), so
  the coarsest sweeps grow with its longest axis: 2 V-cycles left 0.51 of a closed jet with a flat 20
  sweeps, 0.08 with 4 per cell (6 x 128 x 6) and 0.008 (8 x 96 x 8).
- Smoke puff preview on CPU (cloud session, 4 cores): slice 1's Gauss-Seidel 11.7 s, multigrid 8.3 s.
- One smoothing sweep a side diverged next to open faces (38 x 48 x 38, 3 cycles: 0.34), hence the rule
  `multigrid_sweeps >= 2`.
"""

import numpy as np
import pytest
import warp as wp

from plume.recipe.schema import FaceSettings
from plume.sim.multigrid import Multigrid, coarse_cells, residual_kernel
from plume.sim.pressure import GaussSeidel, compute_divergence, project
from support.grids import ALL_CLOSED, blob, fill, small_grid

OPEN = FaceSettings()  # floor closed, the rest open


def jet_grid(cells, faces):
    grid = small_grid("cpu", cells=cells, faces=faces)
    shape = grid.v.data.shape
    fill(grid.v.data, blob(shape, [n / 2 for n in shape], min(cells) / 5))
    return grid


def divergence_left(grid, solve):
    project(grid, GaussSeidel(0))  # zero the closed walls before measuring
    before = np.linalg.norm(compute_divergence(grid).numpy())
    project(grid, solve)
    return np.linalg.norm(compute_divergence(grid).numpy()) / before


def poisson_residual(multigrid):
    top = multigrid.levels[0]
    wp.launch(residual_kernel, dim=top.cells, device="cpu", inputs=[top.q, top.rhs, top.residual, top.info])
    return float(np.linalg.norm(top.residual.numpy()) / np.linalg.norm(top.rhs.numpy()))


@pytest.mark.parametrize("faces", [ALL_CLOSED, OPEN], ids=["closed", "open"])
@pytest.mark.parametrize("cells", [(32, 32, 32), (31, 33, 29)], ids=["even", "odd"])
def test_two_cycles_beat_sixty_gauss_seidel_sweeps(cpu_device, cells, faces):
    multigrid_left = _multigrid_left(cells, faces)
    gauss_seidel_left = divergence_left(jet_grid(cells, faces), GaussSeidel(60))
    # Measured: closed 0.010 and 0.013 against 1.04 and 0.92; open 0.054 and 0.036 against 0.36 and 0.27.
    assert multigrid_left < 0.1
    assert multigrid_left < 0.25 * gauss_seidel_left


@pytest.mark.parametrize("faces", [ALL_CLOSED, OPEN], ids=["closed", "open"])
def test_each_cycle_shrinks_the_residual_on_an_odd_grid(cpu_device, faces):
    grid = jet_grid((15, 17, 13), faces)
    project(grid, GaussSeidel(0))
    compute_divergence(grid)
    multigrid = Multigrid(grid, 1, 2)
    residuals = []
    for _ in range(4):
        multigrid(grid)
        residuals.append(poisson_residual(multigrid))
    assert residuals[-1] < 0.01
    # Every cycle after the first at least halves it (measured about 0.2 a cycle); the first cycle with
    # open faces only reaches about 0.9 of the start, because the cold start's error sits at the faces.
    assert all(later < 0.5 * earlier for earlier, later in zip(residuals, residuals[1:]))


def test_levels_halve_down_to_a_few_cells(cpu_device):
    grid = small_grid("cpu", cells=(38, 48, 38))
    cells = [level.cells for level in Multigrid(grid, 1, 2).levels]
    assert cells == [(38, 48, 38), (19, 24, 19), (10, 12, 10), (5, 6, 5), (3, 3, 3), (2, 2, 2)]
    assert coarse_cells((5, 6, 5)) == (3, 3, 3)


def test_closed_walls_stay_exactly_zero(cpu_device):
    grid = jet_grid((16, 16, 16), OPEN)
    rng = np.random.default_rng(3)
    for field in grid.velocity_fields():
        fill(field.data, rng.normal(size=field.data.shape))
    project(grid, Multigrid(grid, 2, 2))
    assert np.all(grid.v.data.numpy()[:, 0, :] == 0.0)


def test_same_input_gives_identical_pressure(cpu_device):
    results = []
    for _ in range(2):
        grid = jet_grid((15, 17, 13), OPEN)
        project(grid, Multigrid(grid, 2, 2))
        results.append(grid.pressure.numpy().tobytes())
    assert results[0] == results[1]


def _multigrid_left(cells, faces):
    grid = jet_grid(cells, faces)
    return divergence_left(grid, Multigrid(grid, 2, 2))


def test_a_tall_thin_domain_converges(cpu_device):
    assert divergence_left(jet_grid((6, 96, 6), ALL_CLOSED), _two_cycles) < 0.1


def _two_cycles(grid):
    Multigrid(grid, 2, 2)(grid)
