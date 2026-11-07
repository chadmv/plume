"""Seeded value noise: the only source of randomness in a run.

Lattice values come from an integer hash of (seed, stream, lattice cell), so the same seed always gives the
same pattern on every device, with no random state to carry between kernels.
"""

import warp as wp

# Keeps lattice coordinates positive before they become unsigned; patterns repeat beyond about 2^20 cells.
LATTICE_OFFSET = 1048576


@wp.func
def hash_u32(x: wp.uint32) -> wp.uint32:
    """A well-mixed 32-bit integer hash (the "lowbias32" constants)."""
    x = x ^ (x >> wp.uint32(16))
    x = x * wp.uint32(0x7FEB352D)
    x = x ^ (x >> wp.uint32(15))
    x = x * wp.uint32(0x846CA68B)
    x = x ^ (x >> wp.uint32(16))
    return x


@wp.func
def lattice_value(seed: int, stream: int, i: int, j: int, k: int) -> float:
    """A value in -1..1 fixed by the seed, the stream (for example the emitter's index) and the cell."""
    h = hash_u32(wp.uint32(seed + LATTICE_OFFSET))
    h = hash_u32(h ^ wp.uint32(stream + LATTICE_OFFSET))
    h = hash_u32(h ^ wp.uint32(i + LATTICE_OFFSET))
    h = hash_u32(h ^ wp.uint32(j + LATTICE_OFFSET))
    h = hash_u32(h ^ wp.uint32(k + LATTICE_OFFSET))
    return float(h >> wp.uint32(8)) * (2.0 / 16777215.0) - 1.0


@wp.func
def fade(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


@wp.func
def value_noise(seed: int, stream: int, p: wp.vec3) -> float:
    """Smooth noise in -1..1 with one lattice cell per unit of `p`."""
    fx = wp.floor(p[0])
    fy = wp.floor(p[1])
    fz = wp.floor(p[2])
    i = int(fx)
    j = int(fy)
    k = int(fz)
    tx = fade(p[0] - fx)
    ty = fade(p[1] - fy)
    tz = fade(p[2] - fz)
    c00 = wp.lerp(lattice_value(seed, stream, i, j, k), lattice_value(seed, stream, i + 1, j, k), tx)
    c10 = wp.lerp(lattice_value(seed, stream, i, j + 1, k), lattice_value(seed, stream, i + 1, j + 1, k), tx)
    c01 = wp.lerp(lattice_value(seed, stream, i, j, k + 1), lattice_value(seed, stream, i + 1, j, k + 1), tx)
    c11 = wp.lerp(lattice_value(seed, stream, i, j + 1, k + 1),
                  lattice_value(seed, stream, i + 1, j + 1, k + 1), tx)
    return wp.lerp(wp.lerp(c00, c10, ty), wp.lerp(c01, c11, ty), tz)
