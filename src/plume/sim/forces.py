"""Body forces on the gas. Slice 1 has buoyancy: hot gas rises, smoke weighs it down."""

import warp as wp

from plume.sim.grid import Grid, GridInfo


@wp.kernel
def buoyancy_kernel(v: wp.array3d(dtype=float), smoke: wp.array3d(dtype=float),
                    temperature: wp.array3d(dtype=float), info: GridInfo, gravity: float, heat_buoyancy: float,
                    smoke_weight: float, ambient_k: float, dt: float):
    i, j, k = wp.tid()
    below = wp.max(j - 1, 0)
    above = wp.min(j, info.dims[1] - 1)
    heat = 0.5 * (temperature[i, below, k] + temperature[i, above, k])
    density = 0.5 * (smoke[i, below, k] + smoke[i, above, k])
    lift = heat_buoyancy * (heat - ambient_k) / ambient_k - smoke_weight * density
    v[i, j, k] = v[i, j, k] + gravity * lift * dt


def apply_buoyancy(grid: Grid, gravity: float, heat_buoyancy: float, smoke_weight: float, ambient_k: float,
                   dt: float) -> None:
    """Vertical acceleration `gravity * (heat_buoyancy * (T - ambient) / ambient - smoke_weight * smoke)`."""
    wp.launch(buoyancy_kernel, dim=grid.v.data.shape, device=grid.device,
              inputs=[grid.v.data, grid.smoke.data, grid.temperature.data, grid.info, gravity, heat_buoyancy,
                      smoke_weight, ambient_k, dt])
