"""The simulation grid: a MAC (staggered) grid with face velocities and centered scalars.

Positions inside kernels are in cell units with 0 at the domain's minimum corner. A field's samples sit
at `index + offset`: centered scalars at offset (0.5, 0.5, 0.5), x-face velocity `u` at (0, 0.5, 0.5),
and so on.
"""

from dataclasses import dataclass

import warp as wp

from plume.recipe.derived import Derived
from plume.recipe.schema import FaceSettings

CENTER = wp.vec3(0.5, 0.5, 0.5)
U_FACE = wp.vec3(0.0, 0.5, 0.5)
V_FACE = wp.vec3(0.5, 0.0, 0.5)
W_FACE = wp.vec3(0.5, 0.5, 0.0)


@wp.struct
class GridInfo:
    dims: wp.vec3i
    cell_m: float
    origin_m: wp.vec3
    open_lo: wp.vec3i
    open_hi: wp.vec3i


class AdvectedField:
    """One advected quantity: its current values and the scratch arrays MacCormack needs."""

    def __init__(self, shape: tuple[int, int, int], offset: wp.vec3, outside: float, uses_outside: bool,
                 device: str, initial: float = 0.0):
        self.offset = offset
        self.outside = outside
        self.uses_outside = 1 if uses_outside else 0
        self.data = wp.full(shape, initial, dtype=float, device=device)
        self.hat = wp.zeros(shape, dtype=float, device=device)
        self.back = wp.zeros(shape, dtype=float, device=device)
        self.next = wp.zeros(shape, dtype=float, device=device)

    def swap(self) -> None:
        """Makes the freshly advected values current."""
        self.data, self.next = self.next, self.data


@dataclass
class Grid:
    info: GridInfo
    device: str
    cells: tuple[int, int, int]
    u: AdvectedField
    v: AdvectedField
    w: AdvectedField
    smoke: AdvectedField
    temperature: AdvectedField
    pressure: wp.array
    divergence: wp.array

    def velocity_fields(self) -> tuple[AdvectedField, AdvectedField, AdvectedField]:
        return self.u, self.v, self.w


def make_grid(derived: Derived, cell_m: float, faces: FaceSettings, ambient_k: float, device: str) -> Grid:
    """Allocates a grid at rest, filled with ambient air."""
    nx, ny, nz = derived.cells
    info = GridInfo()
    info.dims = wp.vec3i(nx, ny, nz)
    info.cell_m = cell_m
    info.origin_m = wp.vec3(*derived.domain_min_m)
    info.open_lo = wp.vec3i(*(_is_open(kind) for kind in (faces.left, faces.bottom, faces.back)))
    info.open_hi = wp.vec3i(*(_is_open(kind) for kind in (faces.right, faces.top, faces.front)))
    center_shape = (nx, ny, nz)
    return Grid(
        info=info,
        device=device,
        cells=(nx, ny, nz),
        u=AdvectedField((nx + 1, ny, nz), U_FACE, 0.0, False, device),
        v=AdvectedField((nx, ny + 1, nz), V_FACE, 0.0, False, device),
        w=AdvectedField((nx, ny, nz + 1), W_FACE, 0.0, False, device),
        smoke=AdvectedField(center_shape, CENTER, 0.0, True, device),
        temperature=AdvectedField(center_shape, CENTER, ambient_k, True, device, initial=ambient_k),
        pressure=wp.zeros(center_shape, dtype=float, device=device),
        divergence=wp.zeros(center_shape, dtype=float, device=device),
    )


def _is_open(kind: str) -> int:
    return 1 if kind == "open" else 0
