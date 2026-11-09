import numpy as np
import pytest

from plume.recipe.derived import derive
from plume.recipe.schema import EmitterSettings, FaceSettings
from plume.view.guides import (DASH_PX, GAP_PX, BOX, EMITTER, LIGHT, TICK, Segment, box_edges, clip_to_rect,
                               dashes, emitter_outline, floor_ticks, guide_segments, on_screen)
from plume.view.navigation import Navigation
from support.recipes import tiny_recipe

LOW = np.array([-1.0, 0.0, -1.0])
SIZE = np.array([2.0, 2.5, 2.0])


def test_a_closed_floor_under_open_walls_has_a_solid_outline_and_dashed_walls():
    edges = box_edges(LOW, SIZE, FaceSettings())  # floor closed, the rest open
    assert len(edges) == 12
    on_floor = [edge.start[1] == 0.0 and edge.end[1] == 0.0 for edge in edges]
    assert sum(on_floor) == 4
    assert all(edge.dashed != floor for edge, floor in zip(edges, on_floor, strict=True))
    closed_front = box_edges(LOW, SIZE, FaceSettings(front="closed"))
    assert sum(not edge.dashed for edge in closed_front) == 7  # 4 floor + 3 more round the front


def test_floor_ticks_sit_on_every_half_meter_along_each_floor_edge():
    ticks = floor_ticks(LOW, SIZE)
    along_x = sorted({float(tick.start[0]) for tick in ticks if tick.start[2] == -1.0})
    assert along_x == [-1.0, -0.5, 0.0, 0.5, 1.0]
    assert len(ticks) == 4 * 5
    assert all(tick.start[1] == 0.0 and tick.end[1] == 0.0 for tick in ticks)


def test_an_emitter_is_dashed_for_a_block_it_was_off_for():
    puff = EmitterSettings(name="puff", center_m=(0.0, 0.3, 0.0), radius_m=0.2, start_s=0.1, end_s=0.5)
    assert not any(segment.dashed for segment in emitter_outline(puff, 0.4, 0.6))
    assert all(segment.dashed for segment in emitter_outline(puff, 0.5, 0.7))
    assert all(segment.dashed for segment in emitter_outline(puff, 0.0, 0.1))
    circle = emitter_outline(puff, 0.4, 0.6)
    radii = [np.linalg.norm(segment.start - np.array(puff.center_m)) for segment in circle]
    assert radii == pytest.approx([0.2] * len(radii))
    box = EmitterSettings(name="box", shape="box", center_m=(0.0, 0.3, 0.0), size_m=(0.4, 0.2, 0.4), end_s=1.0)
    assert len(emitter_outline(box, 0.0, 0.1)) == 12


def test_guide_segments_for_a_run_have_every_kind():
    recipe = tiny_recipe()
    kinds = {segment.kind for segment in guide_segments(recipe, derive(recipe), 0, np.array([0.0, 1.0, 1.0]))}
    assert kinds == {BOX, TICK, EMITTER, LIGHT}


def test_a_segment_crossing_behind_the_eye_is_clipped_and_one_wholly_behind_is_dropped():
    nav = Navigation(LOW, SIZE)
    nav.set_viewport(100, 100)
    nav.toggle_perspective()
    camera = nav.view_camera()
    eye, toward = camera.eye, camera.toward
    behind = Segment(eye + toward, eye + toward * 2, False, BOX)
    assert on_screen(camera, behind) is None
    crossing = on_screen(camera, Segment(eye + toward + camera.right * 0.1, nav.pivot, False, BOX))
    assert crossing is not None and all(np.isfinite(value) for point in crossing for value in point)
    assert crossing[1] == pytest.approx((50.0, 50.0))


def test_dashes_cover_the_line_in_dash_and_gap_steps():
    pieces = dashes((0.0, 0.0), (30.0, 0.0))
    assert pieces[0] == ((0.0, 0.0), (DASH_PX, 0.0))
    assert pieces[1][0] == (DASH_PX + GAP_PX, 0.0)
    assert pieces[-1][1] == (30.0, 0.0)


def test_screen_segments_are_clipped_to_the_viewport_before_dashing():
    assert clip_to_rect((-100.0, 50.0), (200.0, 50.0), 0.0, 0.0, 100.0, 100.0) == ((0.0, 50.0), (100.0, 50.0))
    assert clip_to_rect((-100.0, -5.0), (200.0, -5.0), 0.0, 0.0, 100.0, 100.0) is None
    nav = Navigation(LOW, SIZE)
    nav.set_viewport(1600, 900)
    nav.toggle_perspective()
    nav.pivot = np.array([0.3, 1.0, 0.4]) - nav.basis()[2] * nav.distance  # the eye inside the box
    camera = nav.view_camera()
    pieces = 0
    for segment in box_edges(LOW, SIZE, FaceSettings()):
        ends = on_screen(camera, segment)
        if ends is not None:
            pieces += len(dashes(*ends))
    assert pieces < 2000  # unclipped, the edges near the eye split into tens of thousands of dashes
