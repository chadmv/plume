---
date: 2026-11-09
topic: viewer-v3-inspect
branch: claude/project-thread-vz72ja
range: 3a4eca3..HEAD
---

# Session Retro: 2026-11-09 - Live viewer slice V3 Inspect

**TL;DR:** `plume view` can now inspect, not just watch and tune. `Tab` switches the viewport to a **Sheet**
tab that plays the assembled flipbook on a card facing the camera, with the contact sheets' look over the
chosen background, whole frames at the sheet's fps; at Home the card sits exactly over the volume's smoke.
`plume view out/<name>/` opens a finished sheet folder in that tab alone, with no GPU and no simulation. A
**numbers strip** under the view plots coverage, mean thickness and peak heat per frame (the `numbers.txt`
numbers), marks frames whose smoke reaches an open face or the ceiling and frames the step cap split, and
its playhead line can be dragged. The **slice plane** (`L`, left drag to move) colors smoke, temperature,
speed or swirl on a plane through the domain with a legend; the frame cache now keeps each frame's velocity
for it, and drops velocity before any frame when `--cache-gb` is short. **Still** (`F12`) and **Save clip**
write PNGs and animated PNGs into `out/<name>/view/` (or `--out`'s) with a `.toml` naming the camera, frame,
view and resolved recipe, so a thread can read exactly what was seen. `plume run`'s outputs are unchanged
(the raw-frame digest test holds). Cloud: 307 tests pass (2 gpu tests skip) and both windows were smoke-run
under `xvfb-run`, saving stills and clips. Not yet done: the PC run (gpu tests, the controls by hand) and the
user's look at it, which ends the slice.

## Handoff

- Built from `docs/specs/2026-11-08-live-viewer-design.md` slice V3 (section 10); plan
  `docs/plans/2026-11-09-viewer-v3-inspect.md` (TV3.1 to TV3.7; "Corrections to inputs" lists every
  deviation from the spec).
- New: `view/slice_plane.py`, `sheet_player.py`, `sheet_app.py` (the sheet-only window), `numbers_strip.py`,
  `transport.py`, `capture.py`, `camera_input.py` and `window_parts.py` (the last two shared by both windows).
- Changed: `render/raymarch.py` (`pixel_ray` as a `wp.func`, shared with the slice kernel; no byte change),
  `view/frame_cache.py` (velocity, budget order), `view/live_run.py` (faces reached per frame,
  `visible_density`), `view/navigation.py` (`pose_table`, `set_pose`), `recipe/serialize.py`
  (`recipe_table`), `view/app.py`, `cli/view.py` and `cli/main.py` (`--out`, a folder opens the sheet).
- For the PC: `uv sync --extra view`, then `uv run plume view recipes/smoke_puff.toml`: let it run, press
  `Tab` to the Sheet tab, `L` for the slice (try swirl), drag the strip's playhead, Save clip; and
  `uv run plume run recipes/smoke_puff.toml` then `uv run plume view out/smoke_puff/`. The slice's redraw time
  with the slice on is worth a glance against V17 (the legend's range is read on the host each new frame).
- Done when (spec section 10): the user has judged one recipe's sheet in the Sheet tab and saved a clip that
  a thread read back. Then the viewer's backlog item can close.

## What Was Built

- Velocity at cell centers (16-bit vectors, the simulation's own centering) in the frame cache; the plan is
  every frame with velocity, else every frame without, else thinned frames without.
- Faces reached per landed frame: a gather kernel copies the six boundary layers, numpy takes their largest
  values, and an open face or the ceiling counts at one byte step of visible smoke.
- The slice kernel casts the march's own pixel rays, meets the axis plane, samples a prepared 32-bit field
  (speed and swirl via the simulation's `curl_kernel`), and dims the volume elsewhere; the legend's range is
  the whole frame's, so it stays put while the plane moves.
- The Sheet tab drawn on the host as one image (background, then the composited cell resized bilinearly
  into its place, only the visible part), so the screen, stills and clips share one drawing.

## Key Decisions

- **The card is a camera-facing billboard seated on the seat emitter's center**, side `frame_m`. With Home's
  orthographic sheet camera it lands on the crop exactly (a test pins it), which makes the Sheet tab and the
  Volume tab line up for comparison.
- **The strip's numbers come from the sheet** (`measure` of the assembled frames), so they appear when the
  run's sheet does; during a run the strip shows only the edge marks.
- **Clips and stills redraw at full size without guides or text.** One image per kept frame (Volume) or
  sheet frame (Sheet); Split saves both panes side by side.
- **A sheet folder's look comes from its `settings.toml`**, else the schema's default look with a banner.
- **Capture `.toml` paths are repo-relative** (`source_path`, as the sheet JSON's `source`), not machine paths.

## What Went Wrong and What Changes

- **The window smoke run caught a crash the unit tests did not:** a card whose rounded pixel edges passed its
  own size made Pillow's `resize(box=...)` raise. Fixed by clamping the source box, with a test. Rule kept
  from V2: smoke-run the window under `xvfb-run` before review, driving each new control by script.
- **The review found a real staleness bug:** the Sheet tab kept the old look after a `[look]` edit, because
  a look edit keeps the run and the card was cached by run. Cards are now keyed on the run and the viewport
  (a look edit makes a new viewport). Also fixed from the review: Split now shows a legend per pane (each
  pane's range is its own) and none when a pane has no slice; F in the sheet-only window frames the card,
  not its seat; capture counters for names holding glob characters; a sheet JSON with wrong types is
  refused rather than crashing; the plan's exit code for a folder with no sheet (64, the usage error).
- **Commits are by file group, not one per task:** `app.py` wires every task, so it landed in one commit
  after the parts it imports.

## Recommended Backlog Items

- Filed `docs/backlog/idea-2026-11-09-viewer-v3-small-cleanups.md`: the slice legend's host copy, fast
  clips from a thinned cache, a stronger edge-mark test, and `app.py`'s size.

## Files Most Touched

`src/plume/view/app.py`, `sheet_player.py`, `slice_plane.py`, `sheet_app.py`, `frame_cache.py`,
`capture.py`; `tests/view/test_sheet_player.py`, `test_slice_plane.py`, `test_capture.py`.
