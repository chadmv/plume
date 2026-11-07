"""Emitters: sources that add smoke and hold temperature and velocity inside a soft-edged shape.

Every emitter kernel gathers: each cell or face loops over the emitters, so no two threads ever write the
same value and results are deterministic.
"""

import warp as wp

from plume.recipe.schema import EmitterSettings
from plume.sim.grid import U_FACE, V_FACE, W_FACE, Grid, GridInfo
from plume.sim.noise import value_noise

SPHERE = 0
BOX = 1


@wp.struct
class EmitterParams:
    shape: int
    center_m: wp.vec3
    radius_m: float
    half_size_m: wp.vec3
    edge_softness: float
    start_s: float
    end_s: float
    smoke_per_s: float
    temperature_k: float
    velocity_mps: wp.vec3
    outward: int
    noise_scale_m: float
    noise_strength: float
    stream: int


@wp.func
def soft_edge(distance: float, extent: float, softness: float) -> float:
    """1 inside, falling smoothly to 0 across the outer `softness` fraction of `extent`."""
    inner = extent * (1.0 - softness)
    if distance <= inner:
        return 1.0
    if distance >= extent:
        return 0.0
    t = (distance - inner) / (extent - inner)
    return 1.0 - t * t * (3.0 - 2.0 * t)


@wp.func
def coverage(e: EmitterParams, x: wp.vec3, seed: int) -> float:
    """How fully the emitter covers world point `x`, 0 to 1 before noise breakup."""
    offset = x - e.center_m
    amount = 0.0
    if e.shape == 0:
        amount = soft_edge(wp.length(offset), e.radius_m, e.edge_softness)
    else:
        amount = (soft_edge(wp.abs(offset[0]), e.half_size_m[0], e.edge_softness)
                  * soft_edge(wp.abs(offset[1]), e.half_size_m[1], e.edge_softness)
                  * soft_edge(wp.abs(offset[2]), e.half_size_m[2], e.edge_softness))
    if amount > 0.0 and e.noise_strength > 0.0:
        breakup = 1.0 + e.noise_strength * value_noise(seed, e.stream, x / e.noise_scale_m)
        amount = amount * wp.max(breakup, 0.0)
    return wp.min(amount, 1.0)


@wp.func
def is_active(e: EmitterParams, time_s: float) -> bool:
    return time_s >= e.start_s and time_s < e.end_s


@wp.func
def world_position(info: GridInfo, index: wp.vec3) -> wp.vec3:
    return info.origin_m + index * info.cell_m


@wp.kernel
def emit_scalars_kernel(smoke: wp.array3d(dtype=float), temperature: wp.array3d(dtype=float),
                        emitters: wp.array(dtype=EmitterParams), info: GridInfo, seed: int, time_s: float,
                        dt: float):
    i, j, k = wp.tid()
    x = world_position(info, wp.vec3(float(i), float(j), float(k)) + wp.vec3(0.5, 0.5, 0.5))
    for n in range(emitters.shape[0]):
        e = emitters[n]
        if is_active(e, time_s):
            amount = coverage(e, x, seed)
            if amount > 0.0:
                smoke[i, j, k] = smoke[i, j, k] + e.smoke_per_s * amount * dt
                temperature[i, j, k] = wp.lerp(temperature[i, j, k], e.temperature_k, amount)


@wp.kernel
def emit_velocity_kernel(component: wp.array3d(dtype=float), axis: int, offset: wp.vec3,
                         emitters: wp.array(dtype=EmitterParams), info: GridInfo, seed: int, time_s: float):
    i, j, k = wp.tid()
    x = world_position(info, wp.vec3(float(i), float(j), float(k)) + offset)
    for n in range(emitters.shape[0]):
        e = emitters[n]
        if is_active(e, time_s):
            amount = coverage(e, x, seed)
            if amount > 0.0:
                target = e.velocity_mps
                if e.outward == 1:
                    away = x - e.center_m
                    if wp.length(away) > 0.0:
                        target = wp.normalize(away) * wp.length(e.velocity_mps)
                component[i, j, k] = wp.lerp(component[i, j, k], target[axis], amount)


def emitter_params(emitters: tuple[EmitterSettings, ...], device: str) -> wp.array:
    """The recipe's emitters as a device array, each with its own noise stream (its index)."""
    params = []
    for index, settings in enumerate(emitters):
        p = EmitterParams()
        p.shape = SPHERE if settings.shape == "sphere" else BOX
        p.center_m = wp.vec3(*settings.center_m)
        p.radius_m = settings.radius_m
        p.half_size_m = wp.vec3(*(size / 2 for size in settings.size_m))
        p.edge_softness = settings.edge_softness
        p.start_s = settings.start_s
        p.end_s = settings.end_s
        p.smoke_per_s = settings.smoke_per_s
        p.temperature_k = settings.temperature_k
        p.velocity_mps = wp.vec3(*settings.velocity_mps)
        p.outward = 1 if settings.velocity_mode == "outward" else 0
        p.noise_scale_m = settings.noise.scale_m
        p.noise_strength = settings.noise.strength
        p.stream = index
        params.append(p)
    return wp.array(params, dtype=EmitterParams, device=device)


def emit(grid: Grid, emitters: wp.array, seed: int, time_s: float, dt: float) -> None:
    """Applies every emitter active at `time_s` for one step of length `dt`."""
    wp.launch(emit_scalars_kernel, dim=grid.cells, device=grid.device,
              inputs=[grid.smoke.data, grid.temperature.data, emitters, grid.info, seed, time_s, dt])
    for axis, (field, offset) in enumerate(zip(grid.velocity_fields(), (U_FACE, V_FACE, W_FACE))):
        wp.launch(emit_velocity_kernel, dim=field.data.shape, device=grid.device,
                  inputs=[field.data, axis, offset, emitters, grid.info, seed, time_s])

