"""Pins one raw frame's bytes in both layouts, so a change to the ray march (the viewer's camera input) or
to the light volume cannot move a sheet's bytes unnoticed.

The digests were taken at commit 626d5d9, before the camera input, on Linux CPU. They pin this platform's
CPU kernels; a platform whose CPU gives other bytes needs its own digests, also taken before a change.
"""

import hashlib
import platform

import pytest

from plume.recipe.derived import derive
from plume.recipe.schema import NORMAL_LAYOUT, SHADE_LAYOUT
from plume.render.camera import make_camera, make_domain_view
from plume.render.frame_renderer import FrameRenderer
from plume.sim.run import simulate
from support.recipes import tiny_recipe

DIGESTS = {
    "Linux": {
        SHADE_LAYOUT: "9a79a4edcc3e2201d481b79d6a06229d7382b8192a7a36f8b3a4ec403492f334",
        NORMAL_LAYOUT: "8e2bf0959a8e48642b880cab48a2ff6360ad40ad013434f0a9689e121dc9711f",
    },
}


def last_raw_frame(channels: str):
    recipe = tiny_recipe(emitter=[{"name": "puff", "center_m": [0.0, 0.3, 0.0], "radius_m": 0.2, "end_s": 0.5,
                                   "smoke_per_s": 5.0, "temperature_k": 900.0}],
                         camera={"elevation_deg": 20.0, "azimuth_deg": 30.0}, output={"channels": channels})
    derived = derive(recipe)
    view = make_domain_view(make_camera(20.0, 30.0), derived.domain_min_m, derived.size_m, recipe.domain.cell_m,
                            recipe.render.px_per_cell)
    renderer = FrameRenderer(view, recipe.render, derived.cells, channels, "cpu")
    frames = []
    simulate(recipe, derived, "cpu", lambda frame, grid: frames.append(renderer.render(grid)))
    return frames[-1]


@pytest.mark.parametrize("channels", [SHADE_LAYOUT, NORMAL_LAYOUT])
def test_raw_frame_bytes_are_unchanged(cpu_device, channels):
    digests = DIGESTS.get(platform.system())
    if digests is None:
        pytest.skip(f"no raw frame digests recorded for {platform.system()} CPU")
    frame = last_raw_frame(channels)
    assert frame.shape == (68, 66, 5)
    assert hashlib.sha256(frame.tobytes()).hexdigest() == digests[channels]
