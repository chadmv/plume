"""Trilinear sampling of grid fields at continuous positions (cell units, 0 at the domain's corner)."""

import warp as wp

from plume.sim.grid import GridInfo


@wp.func
def sample_index_space(f: wp.array3d(dtype=float), g: wp.vec3) -> float:
    """Trilinear sample at continuous index `g`, clamped to the array's extent."""
    x = wp.clamp(g[0], 0.0, float(f.shape[0] - 1))
    y = wp.clamp(g[1], 0.0, float(f.shape[1] - 1))
    z = wp.clamp(g[2], 0.0, float(f.shape[2] - 1))
    i0 = int(x)
    j0 = int(y)
    k0 = int(z)
    i1 = wp.min(i0 + 1, f.shape[0] - 1)
    j1 = wp.min(j0 + 1, f.shape[1] - 1)
    k1 = wp.min(k0 + 1, f.shape[2] - 1)
    tx = x - float(i0)
    ty = y - float(j0)
    tz = z - float(k0)
    c00 = wp.lerp(f[i0, j0, k0], f[i1, j0, k0], tx)
    c10 = wp.lerp(f[i0, j1, k0], f[i1, j1, k0], tx)
    c01 = wp.lerp(f[i0, j0, k1], f[i1, j0, k1], tx)
    c11 = wp.lerp(f[i0, j1, k1], f[i1, j1, k1], tx)
    return wp.lerp(wp.lerp(c00, c10, ty), wp.lerp(c01, c11, ty), tz)


@wp.func
def range_index_space(f: wp.array3d(dtype=float), g: wp.vec3) -> wp.vec2:
    """Smallest and largest of the eight values a trilinear sample at `g` blends."""
    x = wp.clamp(g[0], 0.0, float(f.shape[0] - 1))
    y = wp.clamp(g[1], 0.0, float(f.shape[1] - 1))
    z = wp.clamp(g[2], 0.0, float(f.shape[2] - 1))
    i0 = int(x)
    j0 = int(y)
    k0 = int(z)
    lo = f[i0, j0, k0]
    hi = lo
    for di in range(2):
        for dj in range(2):
            for dk in range(2):
                value = f[wp.min(i0 + di, f.shape[0] - 1), wp.min(j0 + dj, f.shape[1] - 1),
                          wp.min(k0 + dk, f.shape[2] - 1)]
                lo = wp.min(lo, value)
                hi = wp.max(hi, value)
    return wp.vec2(lo, hi)


@wp.func
def is_outside_open_face(p: wp.vec3, info: GridInfo) -> bool:
    """True when `p` lies beyond a face that is open, where fields take their outside value."""
    for axis in range(3):
        if p[axis] < 0.0 and info.open_lo[axis] == 1:
            return True
        if p[axis] > float(info.dims[axis]) and info.open_hi[axis] == 1:
            return True
    return False


@wp.func
def sample_field(f: wp.array3d(dtype=float), p: wp.vec3, offset: wp.vec3, info: GridInfo, outside: float,
                 uses_outside: int) -> float:
    """Samples a field whose values sit at `index + offset`; beyond open faces it reads `outside`."""
    if uses_outside == 1:
        if is_outside_open_face(p, info):
            return outside
    return sample_index_space(f, p - offset)


@wp.func
def velocity_at(u: wp.array3d(dtype=float), v: wp.array3d(dtype=float), w: wp.array3d(dtype=float),
                p: wp.vec3) -> wp.vec3:
    """Velocity in meters per second at `p`, from the three staggered components."""
    return wp.vec3(
        sample_index_space(u, p - wp.vec3(0.0, 0.5, 0.5)),
        sample_index_space(v, p - wp.vec3(0.5, 0.0, 0.5)),
        sample_index_space(w, p - wp.vec3(0.5, 0.5, 0.0)),
    )
