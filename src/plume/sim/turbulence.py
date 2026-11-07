"""Curl-noise turbulence: a seeded, swirling push that breaks smooth gas into billows (D9).

The push is the curl of a smooth random vector field (three value-noise components from `sim/noise.py`),
so it only stirs the gas and never squeezes it. It is taken as a discrete curl on the grid, from the
potential at each face's four edges, so its discrete divergence is zero and the pressure projection leaves
it alone. Everything is in meters and seconds, so a preview's coarse grid gets the same push as the final
run's (D30):

- `scale_m` is the swirl size: the potential is sampled at `position / scale_m`.
- `strength_mps2` is the push's acceleration: the curl is measured in lattice units, where it is about 1.
- `speed_mps` is how fast the pattern changes: it blends to a fresh pattern every `scale_m / speed_mps`
  seconds, with the same smooth fade the noise uses in space.
"""

import warp as wp

from plume.sim.grid import Grid, GridInfo
from plume.sim.noise import fade, value_noise

# Noise streams for the potential, far above the emitter streams (emitter indices): stream
# `TURBULENCE_STREAM + 3 * time_slice + component`.
TURBULENCE_STREAM = wp.constant(1 << 24)


@wp.func
def potential(seed: int, component: int, p: wp.vec3, pattern_time: float) -> float:
    """One component of the potential at lattice point `p`, blended between time slices."""
    slice_lo = wp.floor(pattern_time)
    blend = fade(pattern_time - slice_lo)
    first = TURBULENCE_STREAM + 3 * int(slice_lo) + component
    return wp.lerp(value_noise(seed, first, p), value_noise(seed, first + 3, p), blend)


@wp.kernel
def turbulence_kernel(f: wp.array3d(dtype=float), axis: int, offset: wp.vec3, info: GridInfo, seed: int,
                      scale_m: float, strength: float, pattern_time: float, dt: float):
    i, j, k = wp.tid()
    face = wp.vec3(float(i), float(j), float(k)) + offset  # cell units
    b = (axis + 1) % 3
    c = (axis + 2) % 3
    half_b = wp.vec3(0.0, 0.0, 0.0)
    half_c = wp.vec3(0.0, 0.0, 0.0)
    half_b[b] = 0.5
    half_c[c] = 0.5
    to_lattice = info.cell_m / scale_m
    # Potential at the face's four edges, in lattice units; the curl over one cell, in lattice units.
    c_plus = potential(seed, c, (face + half_b) * to_lattice, pattern_time)
    c_minus = potential(seed, c, (face - half_b) * to_lattice, pattern_time)
    b_plus = potential(seed, b, (face + half_c) * to_lattice, pattern_time)
    b_minus = potential(seed, b, (face - half_c) * to_lattice, pattern_time)
    curl = ((c_plus - c_minus) - (b_plus - b_minus)) / to_lattice
    f[i, j, k] = f[i, j, k] + strength * curl * dt


FACE_OFFSETS = (wp.vec3(0.0, 0.5, 0.5), wp.vec3(0.5, 0.0, 0.5), wp.vec3(0.5, 0.5, 0.0))


def apply_turbulence(grid: Grid, seed: int, scale_m: float, strength_mps2: float, speed_mps: float,
                     time_s: float, dt: float) -> None:
    """Adds one step of the curl-noise push at time `time_s`; nothing when strength is 0."""
    if strength_mps2 == 0.0:
        return
    pattern_time = time_s * speed_mps / scale_m
    for axis, (field, offset) in enumerate(zip(grid.velocity_fields(), FACE_OFFSETS)):
        wp.launch(turbulence_kernel, dim=field.data.shape, device=grid.device,
                  inputs=[field.data, axis, offset, grid.info, seed, scale_m, strength_mps2, pattern_time, dt])
