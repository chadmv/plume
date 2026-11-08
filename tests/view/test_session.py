"""Section 9's reload tests: following the recipe on disk."""

import os
from pathlib import Path

import pytest

from plume.cli.main import main
from plume.recipe.errors import RecipeError
from plume.view.recipe_watch import POLL_S, RecipeWatch, chain_paths
from plume.view.session import Session
from support.tiny import TINY

PARENT = TINY
CHILD = '''# a child recipe
extends = "parent.toml"

[dissipation]
smoke_per_s = 0.5
'''


def write(path: Path, text: str) -> None:
    path.write_text(text)


def open_session(tmp_path) -> Session:
    write(tmp_path / "parent.toml", PARENT)
    write(tmp_path / "child.toml", CHILD)
    return Session.open(tmp_path / "child.toml", preview=False, sets=(), device="cpu", cache_gb=1.0)


def bump(path: Path, text: str) -> None:
    """Writes the file and makes sure its stamp moves even on a coarse clock."""
    before = path.stat().st_mtime_ns
    write(path, text)
    os.utime(path, ns=(before + 10**9, before + 10**9))


def test_the_watch_covers_the_extends_chain(tmp_path):
    assert chain_paths(tmp_path / "a" / "child.toml", ("../parent.toml", "base/grand.toml")) == [
        tmp_path / "a" / "child.toml", tmp_path / "a" / ".." / "parent.toml",
        tmp_path / "a" / ".." / "base" / "grand.toml"]


def test_a_watch_polls_four_times_a_second_and_reports_a_change_once(tmp_path):
    path = tmp_path / "r.toml"
    write(path, "a")
    watch = RecipeWatch([path])
    start = 1e9
    assert not watch.changed(start)
    bump(path, "b")
    assert not watch.changed(start + POLL_S / 2)  # too soon to look
    assert watch.changed(start + POLL_S)
    assert not watch.changed(start + 2 * POLL_S)


def test_a_parents_change_starts_a_new_run(cpu_device, tmp_path):
    session = open_session(tmp_path)
    first = session.run
    bump(tmp_path / "parent.toml", PARENT.replace("smoke_per_s = 6.0", "smoke_per_s = 4.0"))
    session.update(now_s=1e12)
    assert session.run is not first and session.runs_started == 2
    assert session.recipe.emitter[0].smoke_per_s == 4.0


def test_a_comment_only_edit_does_not_re_run(cpu_device, tmp_path):
    session = open_session(tmp_path)
    first = session.run
    bump(tmp_path / "child.toml", CHILD + "\n# another comment\n")
    session.update(now_s=1e12)
    assert session.run is first and session.error is None


def test_a_recipe_error_keeps_the_last_run_and_shows_what_plume_check_says(cpu_device, tmp_path, capsys):
    session = open_session(tmp_path)
    session.advance()
    first = session.run
    broken = CHILD.replace("smoke_per_s = 0.5", "smoke_per_sec = 0.5")  # an unknown key
    bump(tmp_path / "child.toml", broken)
    session.update(now_s=1e12)
    assert session.run is first and first.landed >= 1
    main(["check", str(tmp_path / "child.toml")])
    assert session.error == capsys.readouterr().err.strip()
    bump(tmp_path / "child.toml", CHILD.replace("0.5", "0.7"))
    session.update(now_s=2e12)
    assert session.error is None and session.run is not first


def test_opening_a_bad_recipe_raises_before_anything_runs(cpu_device, tmp_path):
    write(tmp_path / "bad.toml", TINY.replace("frames = 4", "frames = 0"))
    with pytest.raises(RecipeError):
        Session.open(tmp_path / "bad.toml", preview=False, sets=(), device="cpu", cache_gb=1.0)


def test_the_preview_toggle_re_runs_on_the_preview_grid(cpu_device, tmp_path):
    session = open_session(tmp_path)
    full_cells = session.derived.cells
    session.set_preview(True)
    assert session.runs_started == 2 and session.derived.cells != full_cells


def test_fixing_a_parent_named_by_a_broken_reload_re_runs(cpu_device, tmp_path):
    session = open_session(tmp_path)
    bump(tmp_path / "child.toml", CHILD.replace('"parent.toml"', '"base.toml"'))  # base.toml does not exist yet
    session.update(now_s=1e12)
    assert "recipe not found" in session.error
    write(tmp_path / "base.toml", PARENT.replace("smoke_per_s = 6.0", "smoke_per_s = 4.0"))
    session.update(now_s=2e12)
    assert session.error is None and session.runs_started == 2


def test_an_unreadable_save_is_a_banner_not_a_crash(cpu_device, tmp_path):
    session = open_session(tmp_path)
    (tmp_path / "child.toml").write_bytes(CHILD.encode() + b"# 90\xb0 turn\n")  # not UTF-8
    session.reload()
    assert session.error.startswith("recipe error:") and "not valid TOML" in session.error


def test_a_run_stopped_by_a_recipe_error_keeps_its_frames_and_a_fix_re_runs(cpu_device, tmp_path):
    fast = TINY.replace('noise = {', 'velocity_mps = [0.0, 20.0, 0.0]\nnoise = {') + "\n[solver]\nmax_substeps = 4\n"
    write(tmp_path / "fast.toml", fast)
    session = Session.open(tmp_path / "fast.toml", preview=False, sets=(), device="cpu", cache_gb=1.0)
    for _ in range(4):
        session.advance()
    assert session.run.stopped and session.error.startswith("recipe error:")
    landed, seconds = session.run.landed, session.run_seconds
    assert session.run_seconds == seconds  # the clock stops with the run
    session.advance()
    assert session.run.landed == landed
    bump(tmp_path / "fast.toml", fast.replace("max_substeps = 4", "max_substeps = 128"))
    session.update(now_s=1e12)
    assert session.error is None and not session.run.stopped and session.runs_started == 2


def test_the_preview_toggle_stays_put_when_the_recipe_has_an_error(cpu_device, tmp_path):
    session = open_session(tmp_path)
    bump(tmp_path / "child.toml", CHILD.replace("smoke_per_s = 0.5", "smoke_per_sec = 0.5"))
    session.set_preview(True)
    assert not session.preview and session.error is not None
