"""Rendering a small grid's frame through the real renderer, for render tests."""

from plume.recipe.schema import NORMAL_LAYOUT, RenderSettings
from plume.render.camera import make_camera, make_domain_view
from plume.render.frame_renderer import FrameRenderer

CELL_M = 0.1
CELLS = (16, 16, 16)


def render(grid, elevation_deg=0.0, channels=NORMAL_LAYOUT, **settings):
    """The domain view and raw frame of a 16-cubed grid of 0.1 m cells, at 2 px per cell (32 x 32 px)."""
    view = make_domain_view(make_camera(elevation_deg, 0.0), (-0.8, 0.0, -0.8), (1.6, 1.6, 1.6), CELL_M, 2.0)
    renderer = FrameRenderer(view, RenderSettings(**settings), grid.cells, channels, grid.device)
    return view, renderer.render(grid)
