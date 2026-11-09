---
date: 2026-11-09
topic: viewer-v2-tune
branch: claude/project-thread-8769p5
range: 3f72252..HEAD
---

# Session Retro: 2026-11-09 - Live viewer slice V2 Tune

**TL;DR:** `plume view` can now tune a recipe, not just watch it. A right-hand panel lists every recipe key
by table (defaults dimmed, recipe keys plain, viewer edits highlighted with a Reset); drag a number, pick a
choice or type text and the change applies when you let go, checked by `plume check`'s rules first. What
happens depends on the key's table, which now carries a stage in the schema and the recipe reference: a
simulation key re-runs, a `[render]`, `[camera]` or `[output]` key re-renders the kept frames without
re-running, a `[look]` key only redraws. **Save** (Ctrl+S) writes just the changed keys into the opened
recipe with tomlkit, keeping its comments, layout and line endings, never touching an `extends` parent;
a test proves the saved recipe resolves to exactly what the viewer was showing, so `plume run` of it gives
the same look. **Compare** (`C`) flips to the run before the last change at the same frame and camera,
**Split** shows both side by side, and the panel lists the keys that differ. The light arrow's tip can be
dragged to move the key light. `plume run`'s outputs are unchanged. Cloud: 274 tests pass (2 gpu tests skip) and
the window was smoke-run under `xvfb-run`; the PC run (gpu tests, the controls by hand) is still to do.

## Handoff

- Built from `docs/specs/2026-11-08-live-viewer-design.md` slice V2 (section 10); plan
  `docs/plans/2026-11-09-viewer-v2-tune.md` (TV2.1 to TV2.9; its "Corrections to inputs" lists every
  deviation, the main ones below).
- New: `src/plume/view/recipe_keys.py` (the recipe as flat keys with kind, unit, doc, stage),
  `recipe_writer.py` (Save), `panel.py` (the editing panel); `tomlkit==0.15.2` joins the `view` extra.
- Changed: `recipe/schema.py` (stages, `stage_of`), `recipe/reference.py` and `docs/recipe-reference.md`
  (each table's stage), `recipe/variation.py` (`apply_values`, `set_item`), `recipe/load.py`
  (`resolve_table`), `recipe/rules.py` (emitter names may not hold `.`, `[` or `]`, since key paths name
  emitters by name), `render/frame_renderer.py` (`render_fields`, no byte change), `view/frame_cache.py`
  (each reader widens into its own pair), `view/live_run.py` (re-capture), `view/session.py` (edits,
  stages, A and B, Save), `view/app.py` (panel, Compare, Split, light drag), `view/guides.py` (light drag
  math).
- Not yet done: the PC run (TV2.9): `uv sync --extra view`, `uv run pytest` with the gpu tests, then
  `uv run plume view recipes/smoke_puff.toml` by hand: drag a render value and a simulation value, Compare,
  Split, drag the light arrow, Save. The user's look at it on the PC ends the slice.
- Next: V3 Inspect (the Sheet tab and `plume view OUT_DIR`, the numbers strip, the slice plane, clips and
  stills).

## What Was Built

- Stages on every top-level table (simulation, render, sheet, look, preview); a test fails if a new table has
  none.
- A re-capture: a render or sheet edit makes a new run object that shares the finished run's frame cache and
  renders each kept frame's sheet-camera raw frame again, one per window update, then assembles for new
  heat and shade divisors and crop. Playback carries on meanwhile with the old divisors.
- Session work by stage, read off the two resolved recipes; A and B as snapshots (recipe, run, viewport).
- The tomlkit writer: replaced values keep their comment column; a missing top-level table is appended as
  `[table]`, a missing table inside one as an inline table in the recipes' own `{ a = 1 }` style; a parent's
  `[[emitter]]` list is copied into a child that has none before one of its keys is written (lists replace
  whole in `extends`), and Save says so; writes go through a temporary file and a replace, keeping the
  file's mode and any symlink.
- The panel, Compare and Split, the light arrow drag, Ctrl+S and `C`.

## Key Decisions

- **Render and sheet edits re-capture instead of only redrawing.** The spec has them redraw from the kept
  fields, but the sheet camera's raw frames hold the render settings and the camera, and the viewer's heat
  and shade divisors and Home's crop come from them. Re-capturing reads the 16-bit kept fields, so its
  divisors can differ from `plume run`'s in the last digits; the sheet stays `plume run`'s. When the cache
  was thinned or the run is still simulating, the edit re-runs instead.
- **Every edit applies on release, not only simulation edits**, so one drag is one change and one entry for
  Compare.
- **B is a run that got somewhere.** A change while A is still simulating or re-capturing replaces A and
  keeps B.
- **The panel shows the recipe as the file means it** (before `--preview` and dependent defaults), so an
  edit under Preview changes the full-grid value it names.
- **Emitter names must be plain** (no `.`, `[` or `]`): key paths and `--set` name emitters as
  `emitter.<name>.<key>`, and a dotted name could not be addressed. No shipped or test recipe used one.

## What Went Wrong and What Changes

- **The cloud's package download took about 25 minutes** (Warp's 142 MB wheel at well under 1 MB/s), so the
  build ran ahead of the tests; a scratch venv with tomlkit alone ran the writer and key tests meanwhile.
  Rule: start `uv sync --extra view` first thing in a fresh cloud session.
- **The review found four real bugs the tests missed**: Save crashed the window when the file on disk was
  half-typed TOML (tomlkit's own exception); a second render edit during a re-capture made the half-done
  re-capture into B, with stale divisors; a reload whose unsaved edits no longer fit the file (a renamed
  emitter) kept the old file, so Revert could not recover; dotted emitter names could not be edited. Each
  now has a test. Also fixed: the kept-edits banner on the Preview toggle, saved files losing their mode,
  table-valued `--set` edits, the panel recomputing the flat keys five times an update, and `app.py`'s size
  (the panel moved to `panel.py`); the re-check added two small ones (a file error blamed on the edits, an
  edit clearing a banner it did not cause).
- **V1's PC timing probe** (project files `plume-viewer-v1/timing_probe.py`) wraps `app._upload(image)`,
  which is now `_upload(pane, image)`; a PC rerun of it needs that one change.

## Recommended Backlog Items

- None filed. Out of scope from the review: a recipe whose table is split out of order (`[forces]` ...
  `[render]` ... `[forces.turbulence]`) comes back from tomlkit as an out-of-order proxy, and Save refuses it
  with a clear message rather than writing it; worth a look only if a real recipe does that.

## Files Most Touched

`src/plume/view/session.py`, `app.py`, `panel.py`, `recipe_writer.py`, `live_run.py`, `recipe_keys.py`;
`src/plume/recipe/schema.py`; `tests/view/test_session_edits.py`, `test_recipe_writer.py`.
