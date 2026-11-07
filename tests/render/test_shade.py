"""The shade layout's render: the light volume and the shade the camera march gathers from it."""

import math

import numpy as np
import pytest

from plume.recipe.schema import SHADE_LAYOUT
from plume.render.light_volume import LightVolume
from plume.render.raw_frame import SHADE, THICKNESS
from support.grids import blob, fill, small_grid
from support.render import CELL_M, CELLS, render

LEFT = (-1.0, 0.0, 0.0)


def smoke_sphere(device):
    grid = small_grid(device, cells=CELLS, cell_m=CELL_M)
    fill(grid.smoke.data, 3.0 * (blob(CELLS, (8.0, 8.0, 8.0), 3.0) > 0.3))
    return grid


def half_means(image):
    covered = image[..., THICKNESS] > 0.5
    shade = np.where(covered, image[..., SHADE], np.nan)
    return float(np.nanmean(shade[:, :16])), float(np.nanmean(shade[:, 16:]))


def test_light_falls_through_a_uniform_slab_as_beer_lambert(cpu_device):
    grid = small_grid(cpu_device, cells=CELLS, cell_m=CELL_M)
    fill(grid.smoke.data, np.full(CELLS, 0.5))
    light = LightVolume(CELLS, np.array([0.0, 0.0, 1.0]), 2.0, cpu_device).compute(grid).numpy()
    for k in (15, 8, 0):
        depth_m = (CELLS[2] - k - 0.5) * CELL_M  # from the cell center to the +z face
        assert light[8, 8, k] == pytest.approx(math.exp(-2.0 * 0.5 * depth_m), rel=0.01), k


def test_a_sphere_lit_from_the_left_is_darker_on_its_right(cpu_device):
    _, image = render(smoke_sphere(cpu_device), channels=SHADE_LAYOUT, light_dir=LEFT, shade_fill=0.25)
    left, right = half_means(image)
    # Measured: left 0.68, right 0.38 (fill 0.25); the far side sits in the near side's shadow.
    assert left > right + 0.2


def test_full_fill_casts_no_shadow(cpu_device):
    _, image = render(smoke_sphere(cpu_device), channels=SHADE_LAYOUT, light_dir=LEFT, shade_fill=1.0)
    covered = image[..., THICKNESS] > 0.0
    assert np.allclose(image[covered, SHADE], 1.0, atol=1e-5)
    left, right = half_means(image)
    assert left == pytest.approx(right, abs=1e-5)


def test_empty_space_has_no_shade(cpu_device):
    _, image = render(small_grid(cpu_device, cells=CELLS, cell_m=CELL_M), channels=SHADE_LAYOUT)
    assert np.all(image[..., THICKNESS] == 0.0)
    assert np.all(image[..., SHADE] == 0.0)
