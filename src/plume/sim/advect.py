"""Advection: carrying fields along the flow with clamped MacCormack (Selle et al. 2008).

MacCormack runs plain semi-Lagrangian advection backward, then forward again, and uses the round trip's
error to correct the first result. The correction is clamped to the values the backtraced sample blended,
so it never invents new extremes.

Clamped MacCormack does not conserve smoke; `sim/conserve.py` corrects the total after each step.
"""

import warp as wp

from plume.sim.grid import AdvectedField, Grid, GridInfo
from plume.sim.sample import is_outside_open_face, range_index_space, sample_field, velocity_at


@wp.func
def trace(u: wp.array3d(dtype=float), v: wp.array3d(dtype=float), w: wp.array3d(dtype=float), p: wp.vec3,
          dt_over_cell: float) -> wp.vec3:
    """Where a particle at `p` was `dt` ago (second-order midpoint rule). A negative dt traces forward."""
    mid = p - 0.5 * dt_over_cell * velocity_at(u, v, w, p)
    return p - dt_over_cell * velocity_at(u, v, w, mid)


@wp.kernel
def semi_lagrangian_kernel(src: wp.array3d(dtype=float), dst: wp.array3d(dtype=float),
                           u: wp.array3d(dtype=float), v: wp.array3d(dtype=float), w: wp.array3d(dtype=float),
                           info: GridInfo, dt_over_cell: float, offset: wp.vec3, outside: float,
                           uses_outside: int):
    i, j, k = wp.tid()
    p = wp.vec3(float(i), float(j), float(k)) + offset
    dst[i, j, k] = sample_field(src, trace(u, v, w, p, dt_over_cell), offset, info, outside, uses_outside)


@wp.kernel
def maccormack_correct_kernel(original: wp.array3d(dtype=float), hat: wp.array3d(dtype=float),
                              back: wp.array3d(dtype=float), dst: wp.array3d(dtype=float),
                              u: wp.array3d(dtype=float), v: wp.array3d(dtype=float),
                              w: wp.array3d(dtype=float), info: GridInfo, dt_over_cell: float,
                              offset: wp.vec3, outside: float, uses_outside: int):
    i, j, k = wp.tid()
    p = wp.vec3(float(i), float(j), float(k)) + offset
    corrected = hat[i, j, k] + 0.5 * (original[i, j, k] - back[i, j, k])
    source = trace(u, v, w, p, dt_over_cell)
    lo = outside
    hi = outside
    if uses_outside == 0 or not is_outside_open_face(source, info):
        bounds = range_index_space(original, source - offset)
        lo = bounds[0]
        hi = bounds[1]
    dst[i, j, k] = wp.clamp(corrected, lo, hi)


def advect_semi_lagrangian(field: AdvectedField, velocity: tuple[wp.array, wp.array, wp.array], grid: Grid,
                           dt: float) -> None:
    """Plain semi-Lagrangian advection into `field.next` (used by tests as the blurrier baseline)."""
    _launch_trace(field.data, field.next, field, velocity, grid, dt / grid.info.cell_m)


def advect_maccormack(field: AdvectedField, velocity: tuple[wp.array, wp.array, wp.array], grid: Grid,
                      dt: float) -> None:
    """Clamped MacCormack advection of `field.data` into `field.next`."""
    dt_over_cell = dt / grid.info.cell_m
    _launch_trace(field.data, field.hat, field, velocity, grid, dt_over_cell)
    _launch_trace(field.hat, field.back, field, velocity, grid, -dt_over_cell)
    u, v, w = velocity
    wp.launch(maccormack_correct_kernel, dim=field.data.shape, device=grid.device,
              inputs=[field.data, field.hat, field.back, field.next, u, v, w, grid.info, dt_over_cell,
                      field.offset, field.outside, field.uses_outside])


def _launch_trace(src: wp.array, dst: wp.array, field: AdvectedField,
                  velocity: tuple[wp.array, wp.array, wp.array], grid: Grid, dt_over_cell: float) -> None:
    u, v, w = velocity
    wp.launch(semi_lagrangian_kernel, dim=src.shape, device=grid.device,
              inputs=[src, dst, u, v, w, grid.info, dt_over_cell, field.offset, field.outside,
                      field.uses_outside])

