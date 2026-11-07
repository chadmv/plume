import numpy as np

from plume.recipe.schema import FaceSettings
from plume.sim.pressure import compute_divergence, project
from support.grids import fill, small_grid


def randomize_velocity(grid, seed=5):
    rng = np.random.default_rng(seed)
    for field in grid.velocity_fields():
        fill(field.data, rng.normal(size=field.data.shape))


def divergence_norm(grid):
    return float(np.linalg.norm(compute_divergence(grid).numpy()))


def test_projection_removes_most_divergence_with_closed_walls(cpu_device):
    grid = small_grid(cpu_device)
    randomize_velocity(grid)
    project(grid, iterations=0)  # walls closed, nothing solved yet
    before = divergence_norm(grid)
    project(grid, iterations=60)
    assert divergence_norm(grid) < 0.1 * before


def test_projection_removes_most_divergence_with_open_faces(cpu_device):
    grid = small_grid(cpu_device, faces=FaceSettings())  # floor closed, the rest open
    randomize_velocity(grid)
    before = divergence_norm(grid)
    project(grid, iterations=60)
    assert divergence_norm(grid) < 0.1 * before


def test_closed_walls_have_zero_normal_velocity(cpu_device):
    grid = small_grid(cpu_device, faces=FaceSettings())
    randomize_velocity(grid)
    project(grid, iterations=20)
    v = grid.v.data.numpy()
    assert np.all(v[:, 0, :] == 0.0)  # the floor is closed
    assert np.any(v[:, -1, :] != 0.0)  # the top is open
