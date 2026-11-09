"""Section 9's stage and reload tests for V2: edits in the panel, what each stage does, Compare's B, and Save."""

import os
from pathlib import Path

import numpy as np

from plume.recipe.load import load_recipe
from plume.view.session import Session
from support.tiny import TINY

PARENT = TINY
CHILD = '''# a child recipe
extends = "parent.toml"

[dissipation]
smoke_per_s = 0.5   # fades slowly
'''


def open_session(tmp_path: Path, sets: tuple[str, ...] = (), preview: bool = False) -> Session:
    (tmp_path / "parent.toml").write_text(PARENT)
    (tmp_path / "child.toml").write_text(CHILD)
    return Session.open(tmp_path / "child.toml", preview=preview, sets=sets, device="cpu", cache_gb=1.0)


def finish(session: Session) -> None:
    """Captures every frame (simulating or re-capturing) and waits for the sheet assembly."""
    while session.run.capturing:
        session.advance()
    session.run.wait_for_assembly()


def bump(path: Path, text: str) -> None:
    before = path.stat().st_mtime_ns
    path.write_text(text)
    os.utime(path, ns=(before + 10**9, before + 10**9))


def test_a_render_edit_re_captures_and_never_re_runs(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    first = session.run
    assert session.edit("render.opacity_per_density", 8.0) is None
    assert session.runs_started == 1
    run = session.run
    assert run is not first and run.recaptured and run.cache is first.cache
    assert run.simulation_serial == first.simulation_serial
    assert run.heat_divisor == first.heat_divisor  # the source's, until its own assembly lands
    finish(session)
    assert run.landed == run.frames and run.assembled is not None
    thicker = [later[..., 1].sum() > earlier[..., 1].sum()  # THICKNESS
               for later, earlier in zip(run.raw_frames, first.raw_frames, strict=True) if earlier[..., 1].any()]
    assert thicker and all(thicker)
    assert session.compare.run is first  # A became B


def test_a_re_capture_with_unchanged_settings_matches_the_live_run_within_float16(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    first = session.run
    session.edit("output.name", "renamed")  # a sheet key that changes no pixel
    finish(session)
    for recaptured, live in zip(session.run.raw_frames, first.raw_frames, strict=True):
        np.testing.assert_allclose(recaptured, live, rtol=0.0, atol=0.02)


def test_a_look_edit_redraws_over_the_same_run(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    first, viewport = session.run, session.viewport
    assert session.edit("look.shade_depth", 0.5) is None
    assert session.run is first and session.viewport is not viewport and session.runs_started == 1
    assert session.compare.viewport is viewport and session.compare.run is first


def test_a_simulation_edit_re_runs_and_the_old_run_becomes_b(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    first = session.run
    assert session.edit("forces.drag_per_s", 0.3) is None
    assert session.runs_started == 2 and session.run is not first and not session.run.recaptured
    assert session.compare.run is first
    assert session.compare_differences() == ["forces.drag_per_s"]


def test_a_render_edit_while_simulating_re_runs_and_b_stays(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    first = session.run
    session.edit("forces.drag_per_s", 0.3)
    second = session.run
    session.advance()  # the new run is part way
    session.edit("render.soften_px", 1.0)
    assert session.runs_started == 3 and second.stopped
    assert session.compare.run is first  # B is still the run that finished


def test_a_preview_edit_changes_nothing_on_screen_with_preview_off(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    first, viewport = session.run, session.viewport
    assert session.edit("preview.frames", 8) is None
    assert session.run is first and session.viewport is viewport and session.compare is None
    assert session.recipe.preview.frames == 8 and session.edits == {"preview.frames": 8}


def test_a_preview_edit_re_runs_under_preview(cpu_device, tmp_path):
    session = open_session(tmp_path, preview=True)
    assert session.edit("preview.longest_axis_cells", 12) is None
    assert session.runs_started == 2


def test_a_rejected_edit_is_not_applied_and_says_what_plume_check_says(cpu_device, tmp_path):
    session = open_session(tmp_path)
    first = session.run
    error = session.edit("time.frames", 0)
    assert error == "time.frames must be at least 1, got 0"
    assert session.edits == {} and session.run is first and session.recipe.time.frames == 4


def test_an_edit_back_to_the_files_value_drops_the_edit(cpu_device, tmp_path):
    session = open_session(tmp_path)
    session.edit("dissipation.smoke_per_s", 0.7)
    assert session.edits == {"dissipation.smoke_per_s": 0.7}
    session.edit("dissipation.smoke_per_s", 0.5)
    assert session.edits == {}


def test_dragged_floats_are_rounded_and_reset_and_revert_drop_edits(cpu_device, tmp_path):
    session = open_session(tmp_path)
    session.edit("render.soften_px", float(np.float32(0.35)))
    session.edit("render.light_dir", (0.1, 0.9, 0.2))
    assert session.edits == {"render.soften_px": 0.35, "render.light_dir": [0.1, 0.9, 0.2]}
    session.reset("render.soften_px")
    assert list(session.edits) == ["render.light_dir"]
    session.revert()
    assert session.edits == {} and session.recipe.render.light_dir == (-0.5, 0.7, 0.5)


def test_set_values_start_as_edits_with_emitters_by_name(cpu_device, tmp_path):
    session = open_session(tmp_path, sets=("emitter[0].radius_m=0.25", "forces.drag_per_s=0.2"))
    assert session.edits == {"emitter.puff.radius_m": 0.25, "forces.drag_per_s": 0.2}
    assert session.recipe.emitter[0].radius_m == 0.25


def test_unsaved_edits_survive_a_reload_with_a_note(cpu_device, tmp_path):
    session = open_session(tmp_path)
    session.edit("forces.drag_per_s", 0.3)
    bump(tmp_path / "parent.toml", PARENT.replace("smoke_per_s = 6.0", "smoke_per_s = 4.0"))
    session.update(now_s=1e12)
    assert session.recipe.forces.drag_per_s == 0.3 and session.recipe.emitter[0].smoke_per_s == 4.0
    assert session.kept_edits_note == "1 unsaved viewer edit kept over the reloaded recipe"


def test_save_writes_the_edits_and_the_reload_starts_no_run(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    session.edit("forces.drag_per_s", 0.3)
    session.edit("render.soften_px", 1.0)
    finish(session)
    runs, run = session.runs_started, session.run
    assert session.save() == "saved 2 keys to child.toml"
    assert session.edits == {} and session.kept_edits_note is None
    text = (tmp_path / "child.toml").read_text()
    assert text.startswith(CHILD) and (tmp_path / "parent.toml").read_text() == PARENT
    saved = load_recipe(tmp_path / "child.toml")
    assert saved == session.recipe  # the saved recipe runs as the viewer showed it
    session.update(now_s=1e12)  # the watch sees the save
    assert session.runs_started == runs and session.run is run
    assert session.is_set_by_recipe("forces.drag_per_s") and not session.is_set_by_recipe("forces.gravity_mps2")


def test_a_re_run_leaves_the_cache_room_b_does_not_hold(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    held = session.run.cache.stored_bytes
    session.edit("seed", 9)
    assert session.run.cache.budget_bytes == session.budget_bytes - held
    assert session.run.cache.shared_with_compare


def test_a_second_render_edit_during_a_re_capture_keeps_b_and_cancels_the_first(cpu_device, tmp_path):
    session = open_session(tmp_path)
    finish(session)
    first = session.run
    session.edit("render.opacity_per_density", 8.0)
    halfway = session.run
    session.advance()
    session.edit("render.soften_px", 1.0)
    assert session.compare.run is first  # B is still the run that finished
    assert halfway.stopped and session.run.source is first and session.runs_started == 1
    finish(session)
    assert session.run.assembled is not None


def test_save_over_a_file_that_is_not_valid_toml_reports_and_keeps_the_edits(cpu_device, tmp_path):
    session = open_session(tmp_path)
    session.edit("forces.drag_per_s", 0.3)
    (tmp_path / "child.toml").write_text("seed = = 3\n")
    assert session.save().startswith("not saved: cannot save:")
    assert session.edits == {"forces.drag_per_s": 0.3}
    assert (tmp_path / "child.toml").read_text() == "seed = = 3\n"


def test_a_reload_the_edits_no_longer_fit_still_takes_the_file_and_revert_recovers(cpu_device, tmp_path):
    session = open_session(tmp_path)
    session.edit("emitter.puff.radius_m", 0.25)
    bump(tmp_path / "parent.toml", PARENT.replace('name = "puff"', 'name = "blob"').replace("frames = 4", "frames = 5"))
    session.update(now_s=1e12)
    assert "no emitter is named 'puff'" in session.error and "unsaved viewer edits" in session.error
    assert session.revert() is None
    assert session.error is None and session.recipe.time.frames == 5
    assert session.recipe.emitter[0].name == "blob"


def test_the_preview_toggle_does_not_claim_edits_were_kept_over_a_reload(cpu_device, tmp_path):
    session = open_session(tmp_path)
    session.edit("forces.drag_per_s", 0.3)
    session.set_preview(True)
    assert session.kept_edits_note is None


def test_a_table_valued_set_becomes_one_edit_per_key(cpu_device, tmp_path):
    session = open_session(tmp_path, sets=("forces.turbulence={ scale_m = 0.4, strength_mps2 = 0.1 }",))
    assert session.edits == {"forces.turbulence.scale_m": 0.4, "forces.turbulence.strength_mps2": 0.1}
