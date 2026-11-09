"""Section 9's "same frames": the viewer's run is `plume run`'s run, frame for frame."""

import numpy as np
import pytest

from plume.recipe.derived import derive
from plume.render.camera import sheet_domain_view
from plume.render.frame_renderer import FrameRenderer
from plume.sheet.assemble import assemble, seat_point
from plume.sim.run import simulate
from plume.view.live_run import LiveRun
from support.recipes import tiny_recipe

HOT = [{"name": "puff", "center_m": [0.0, 0.3, 0.0], "radius_m": 0.2, "end_s": 0.5, "smoke_per_s": 5.0,
        "temperature_k": 900.0}]


def run_like_plume_run(recipe, derived):
    view = sheet_domain_view(recipe, derived)
    renderer = FrameRenderer(view, recipe.render, derived.cells, recipe.output.channels, "cpu")
    raw_frames, smokes = [], []

    def capture(frame, grid):
        raw_frames.append(renderer.render(grid))
        smokes.append(grid.smoke.data.numpy().copy())

    simulate(recipe, derived, "cpu", capture)
    return raw_frames, smokes, view


@pytest.fixture(scope="module")
def runs(cpu_device):
    recipe = tiny_recipe(emitter=HOT, camera={"elevation_deg": 15.0})
    derived = derive(recipe)
    live = LiveRun(recipe, derived, "cpu", budget_bytes=1e9)
    while live.advance() is not None:
        pass
    live.wait_for_assembly()
    return recipe, derived, live, run_like_plume_run(recipe, derived)


def test_every_frame_matches_plume_runs_raw_frame_byte_for_byte(runs):
    _, _, live, (raw_frames, _, _) = runs
    assert live.done and live.landed == len(raw_frames) == 4
    for viewer_frame, run_frame in zip(live.raw_frames, raw_frames, strict=True):
        assert viewer_frame.tobytes() == run_frame.tobytes()


def test_every_cached_smoke_is_the_runs_smoke_rounded_to_16_bits(runs):
    _, _, live, (_, smokes, _) = runs
    assert live.cache.kept_frames() == [0, 1, 2, 3]
    for frame, smoke in enumerate(smokes):
        assert np.array_equal(live.cache.stored_smoke(frame).numpy(), smoke.astype(np.float16))


def test_the_divisors_are_the_sheets(runs):
    recipe, _, live, (raw_frames, _, view) = runs
    sheet = assemble(raw_frames, view, seat_point(recipe), recipe.output.frame_px, recipe.render,
                     recipe.output.channels)
    assert live.assembled is not None and live.assembly_error is None
    assert live.heat_divisor == sheet.heat_divisor > 0.0
    assert live.shade_divisor == sheet.shade_divisor
    assert live.assembled.crop == sheet.crop
    assert live.steps.total_steps > 0 and live.elapsed_s > 0.0


def test_before_assembly_heat_uses_the_largest_raw_heat_so_far(cpu_device):
    recipe = tiny_recipe(emitter=HOT)
    live = LiveRun(recipe, derive(recipe), "cpu", budget_bytes=1e9)
    live.advance()
    live.advance()
    assert live.heat_divisor == max(float(frame[..., 0].max()) for frame in live.raw_frames)
    assert live.shade_divisor == 1.0
    live.cancel()
    assert not live.done and live.stopped and live.advance() is None


def test_every_frame_notes_the_open_faces_and_ceiling_its_smoke_reached(cpu_device):
    from plume.view.live_run import FACE_NAMES, faces_reached

    recipe = tiny_recipe(domain={"faces": {"left": "closed"}})
    layers = np.zeros((len(FACE_NAMES), 4, 4), dtype=np.float32)
    assert faces_reached(layers, recipe) == ()
    layers[0, 1, 1] = 1.0  # left: closed, so no mark
    layers[2, 0, 0] = 1.0  # bottom: closed
    layers[3, 2, 3] = 1.0  # top: the ceiling
    layers[5, 0, 1] = 1.0  # front: open
    assert faces_reached(layers, recipe) == ("top", "front")


def test_the_boundary_layers_are_the_smokes_outer_cells(cpu_device):
    import warp as wp

    from plume.view.live_run import FACE_NAMES, boundary_layer_kernel

    smoke = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)
    layers = wp.zeros((len(FACE_NAMES), 5, 5), dtype=float, device=cpu_device)
    wp.launch(boundary_layer_kernel, dim=layers.shape, device=cpu_device,
              inputs=[wp.array(smoke, dtype=float, device=cpu_device), layers])
    got = layers.numpy()
    assert np.array_equal(got[0, :4, :5], smoke[0])
    assert np.array_equal(got[1, :4, :5], smoke[-1])
    assert np.array_equal(got[2, :3, :5], smoke[:, 0])
    assert np.array_equal(got[3, :3, :5], smoke[:, -1])
    assert np.array_equal(got[4, :3, :4], smoke[:, :, 0])
    assert np.array_equal(got[5, :3, :4], smoke[:, :, -1])
    assert got[0, 4].sum() == 0.0 and got[2, 3].sum() == 0.0


def test_a_run_keeps_velocity_and_notes_edges_per_frame(runs):
    _, _, live, _ = runs
    assert live.cache.has_velocity and all(live.cache.velocity_kept(frame) for frame in range(4))
    assert sorted(live.edges) == [0, 1, 2, 3]
