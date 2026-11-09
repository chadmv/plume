---
date: 2026-11-08
topic: viewer-v1-watch
branch: claude/project-thread-5tdbx3
range: 626d5d9..HEAD
---

# Session Retro: 2026-11-08 - Live viewer slice V1 Watch

**TL;DR:** `plume view recipes/smoke_puff.toml` now opens a window that runs the recipe and shows the smoke in
3D while it simulates, then loops it, so a run can be judged in motion from any angle: Maya's Alt-drag
tumble, track and dolly, plus a right-mouse free-look with eased WASD/E/Q flying. It draws with the sheet's
own ray march and the contact sheets' look (Look, Heat, Thickness, Shade views, three backgrounds, guides),
and it re-runs when the recipe or a parent is saved; a broken save shows a red banner while the last good run
keeps playing. `plume run` is unchanged: a test pins its raw frames' bytes, and the viewer's frames are
proved byte-identical to `plume run`'s. On the PC (2080 Ti, 1600 x 900) the window redraws 121 times a
second while moving and 64 when still. A whole puff run first took 4.04 s against V17's 4 s; drawing the
landing frames at half size brought it to 3.1 to 3.2 s.

## Handoff

- Built from `docs/specs/2026-11-08-live-viewer-design.md` slice V1 (section 10); plan
  `docs/plans/2026-11-08-viewer-v1-watch.md` (TV1.1 to TV1.12; its "Corrections to inputs" lists every
  deviation from the spec, the main ones below).
- New: `src/plume/view/` (`app`, `session`, `live_run`, `frame_cache`, `navigation`, `viewport`, `guides`,
  `recipe_watch`), `src/plume/cli/view.py`, the `view` extra (imgui-bundle 1.93.0, PyOpenGL 3.1.10, glfw 2.10.0),
  CI installs it.
- Changed: `sim/run.py` (`simulate_frames` generator), `render/raymarch.py` (perspective input),
  `render/frame_renderer.py` (`prepare`/`march`, `domain_view_params`, `toward_light_world`),
  `render/light_volume.py` (takes the smoke array), `render/camera.py` (`sheet_domain_view`),
  `sheet/assemble.py` (`seat_point`), `recipe/variation.py` (unreadable files are recipe errors).
- Tests: 224 on cloud CPU (222 pass, 2 gpu skip). The window was smoke-run in the cloud under `xvfb-run` with
  software OpenGL (live run, playback, perspective, guides, the error banner, free-look capture, F, Home).
- PC run: 224 pass with the gpu tests, none skip. Windows CPU gives other raw-frame bytes than Linux, the
  same before and after the camera input, so both platforms are pinned. A scripted probe drove the window
  on CUDA (the smoke puff's full grid, 1600 x 900): moving, 121 updates a second at the median (79 at the
  95th percentile), 4.6 ms redraws at half resolution; still, 64 a second, 11.8 ms full redraws. A whole run
  took 4.04 s once the kernels were compiled (5.33 s the first time), missing V17's 4 s by 0.04 s; an estimated
  0.75 s of it (64 frames at 11.8 ms) was the full-size redraw of each frame as it lands. With landing frames
  drawn at half size until the run is done (recommended on the user's card), two runs took 3.24 s and 3.07 s,
  and the frame homed after the run is pixel-identical to before. Not yet tried on
  the PC: each control by hand, and the save re-run and error banner (all smoke-run in the cloud).
- Next: the user's look at the viewer on the PC ends the slice; then V2 Tune (stages, the editing panel,
  Save, A/B compare). V1 runs alongside Plume slice 3, so the fireball can be judged in the viewer.

## What Was Built

- A frame loop both commands share: `plume run` and the viewer iterate one generator.
- A perspective camera in the ray march, beside the unchanged orthographic one.
- A live run that simulates one frame per window update, captures it exactly as `plume run` does, keeps its
  smoke and temperature as 16-bit fields under a memory budget, and assembles the sheet on a worker thread
  once done for the sheet's heat and shade divisors and crop.
- The camera: pure math, tested without a window (Home is the sheet camera exactly; the fly eases with
  Petri's 25 and 35 ms time constants, integrated exactly).
- The viewport: march, then a device kernel turns the raw image into display bytes (half resolution while
  the camera moves).
- Guides, the recipe watch with error banners, the Full or Preview toggle, the window and the docs (README
  controls, CLAUDE.md, the look review moving into the viewer, agent folder ownership).

## Key Decisions

- **A live run's landing frames draw at half size** until it is done, then go sharp. The full-size redraw of
  each frame put the first PC run at 4.04 s, over V17's 4 s; the fix went to the user as a card.
- **The look composite runs on the device.** The report's numpy composite took 50 ms at half resolution on the
  cloud CPU, far from 30 redraws a second. The ramps and sRGB curve are tabulated from `report/color.py`;
  the two formula lines are written a second time in the kernel and a parity test holds them within one byte.
- **The march stays 32-bit.** The cache is 16-bit, and a cast kernel widens the drawn frame into scratch
  arrays, so there is still exactly one march kernel.
- **Divisors from a background assembly.** The sheet's own assembly runs on a worker thread (host numpy only;
  every Warp launch stays on the window's thread), so the viewer's heat and shade match the sheet's once it
  lands.
- **Recipe errors exit 2 before the extra is checked**, so a bad recipe reads the same with or without the
  window packages installed.
- **No velocity in V1's cache.** Only the slice plane (V3) reads it.

## What Went Wrong and What Changes

- **Warp's CPU `numpy()` shares memory.** The first viewport test drew the thickness view, then the look view
  into the same scratch, and the thickness array changed under it. Every array handed out of the viewer is
  now a copy. Rule: copy a CPU-device `numpy()` before the next launch can reuse its array.
- **Three review rounds found real bugs the tests missed**: dashed guide edges near a perspective eye split
  into 56,000 dashes (29 ms a frame); a non-UTF-8 save crashed the window; a broken `extends` chain was not
  watched, so fixing the parent did nothing. Each now has a test.
- **The project agents were not available as subagent types** in this cloud session, so the orchestrator
  built every task itself and ran the code-reviewer brief through general-purpose agents in three groups
  (TV1.1-3, TV1.4-8, the whole slice with a security pass).

## Recommended Backlog Items

- Filed: `docs/backlog/idea-2026-11-08-viewer-v1-small-cleanups.md` (an unused sheet image in the viewport,
  the preview toggle re-homing the camera, ruff not in CI).

## Files Most Touched

`src/plume/view/app.py`, `viewport.py`, `navigation.py`, `session.py`, `live_run.py`, `guides.py`;
`src/plume/render/raymarch.py`, `frame_renderer.py`; `tests/view/`.
