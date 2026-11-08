"""The orthographic camera and the domain view: the camera-plane rectangle that covers the whole domain.

Camera space is OpenGL-style: x right, y up, z toward the camera. Elevation tilts the camera to look down;
azimuth orbits it counterclockwise seen from above, starting on the +z side looking along -z.
"""

import math
from dataclasses import dataclass

import numpy as np

from plume.recipe.derived import Derived
from plume.recipe.schema import Recipe


@dataclass(frozen=True)
class Camera:
    right: np.ndarray
    up: np.ndarray
    toward: np.ndarray  # from the scene toward the camera: camera-space +z

    def to_camera_space(self, world_vector: np.ndarray) -> np.ndarray:
        return np.array([world_vector @ self.right, world_vector @ self.up, world_vector @ self.toward])


def make_camera(elevation_deg: float, azimuth_deg: float) -> Camera:
    """The camera's world-space basis for an elevation and azimuth in degrees."""
    elevation = math.radians(elevation_deg)
    azimuth = math.radians(azimuth_deg)
    toward = np.array([math.sin(azimuth) * math.cos(elevation), math.sin(elevation),
                       math.cos(azimuth) * math.cos(elevation)])
    right = np.array([math.cos(azimuth), 0.0, -math.sin(azimuth)])
    up = np.cross(toward, right)
    return Camera(right=right, up=up / np.linalg.norm(up), toward=toward)


@dataclass(frozen=True)
class DomainView:
    """A pixel grid on the camera plane covering the domain's projection. Pixel (0, 0) is top-left."""

    camera: Camera
    left_m: float  # camera-plane x of the left edge
    top_m: float  # camera-plane y of the top edge
    pixel_m: float
    width_px: int
    height_px: int

    def to_pixels(self, world_point: np.ndarray) -> tuple[float, float]:
        """Continuous pixel coordinates (x right, y down) of a world point's projection."""
        x = (world_point @ self.camera.right - self.left_m) / self.pixel_m
        y = (self.top_m - world_point @ self.camera.up) / self.pixel_m
        return float(x), float(y)


def make_domain_view(camera: Camera, domain_min_m: tuple, domain_size_m: tuple, cell_m: float,
                     px_per_cell: float) -> DomainView:
    """The smallest pixel grid, at `px_per_cell` pixels per cell, covering the projected domain box."""
    low = np.array(domain_min_m)
    size = np.array(domain_size_m)
    corners = [low + size * np.array([a, b, c]) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    xs = [corner @ camera.right for corner in corners]
    ys = [corner @ camera.up for corner in corners]
    pixel_m = cell_m / px_per_cell
    return DomainView(
        camera=camera,
        left_m=min(xs),
        top_m=max(ys),
        pixel_m=pixel_m,
        width_px=math.ceil((max(xs) - min(xs)) / pixel_m - 1e-6),
        height_px=math.ceil((max(ys) - min(ys)) / pixel_m - 1e-6),
    )


def sheet_domain_view(recipe: Recipe, derived: Derived) -> DomainView:
    """The sheet camera's domain view of a recipe: what `plume run` renders every frame over."""
    camera = make_camera(recipe.camera.elevation_deg, recipe.camera.azimuth_deg)
    return make_domain_view(camera, derived.domain_min_m, derived.size_m, recipe.domain.cell_m,
                            recipe.render.px_per_cell)
