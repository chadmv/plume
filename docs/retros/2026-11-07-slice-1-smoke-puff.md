---
date: 2026-11-07
topic: slice-1-smoke-puff
branch: claude/plume-fire-simulator-9ea619
range: d76cb44..978cb8c
---

# Session Retro: 2026-11-07 - Slice 1, the smoke puff end to end

**TL;DR:** Plume is a new tool that simulates smoke and fire and renders them as flipbook texture sheets
for a Godot town builder, driven by text recipes that an AI agent edits and reruns. This session ran the
design interview, wrote the design brief, spec and build plan, and built the first working slice: a recipe
for a rising puff of smoke becomes a finished sheet, contact sheets for judging the look, and a file of
per-frame measurements in a few seconds on the GPU. The user approved the puff's look, and its
measurements are now stored so a later change that alters it fails a test.

## Handoff

- Slice 1 (plan tasks T1.1 to T1.14) is complete on `claude/plume-fire-simulator-9ea619` and lands
  through that branch's pull request to `main`. Commits `4c93ccc` (scaffold and docs) through `8fb5969`;
  82 files, about 4,700 lines.
- Stack: Python 3.13, `warp-lang==1.19.0` (pinned), numpy, Pillow, tomli-w, uv. Warp runs in
  `wp.DeterministicMode.RUN_TO_RUN` with `log_level = wp.LOG_WARNING` (1.19 has no `wp.config.quiet`);
  see `sim/device.py`.
- Tests: 60 pass locally in about 19 s, including the `gpu`-marked CPU against CUDA test. CI
  (`.github/workflows/ci.yml`, Ubuntu, CPU) runs `pytest -m "not gpu"` and the CPU preview; its first run
  is on this branch's pull request. WSL Ubuntu here has no uv (Python 3.8 only), so CI is the Linux check.
- Golden: `tests/golden/smoke_puff_preview.numbers.txt` is a CUDA preview of the committed
  `recipes/smoke_puff.toml`; `tests/cli/test_golden_numbers.py` reruns it on CPU (about 10 s) and compares
  within 2 percent (amounts), 0.02 (box edges) and one frame (peak and fade). CPU and CUDA previews agree
  to the fourth decimal.
- Measured with kernels cached, wall clock: GPU preview 2.4 s, GPU full sheet 6.5 s (80 x 100 x 80 cells,
  64 frames, 256 px), CPU preview 9.9 s. First run per device compiles for about 20 s. Recorded in spec
  section 11.
- The approved puff: peak frame 5, fade frame 61 of 64, `frame_m` 1.539, seat (0.504, 0.776). Known look
  limits the user accepted: it rolls into a dome (a vortex ring) until slice 2 adds turbulence; it fills
  about half the frame width because the crop covers its whole climb; it is faint on the neutral contact
  sheet.
- Spec amendments A1 (keep 2D frame images, not volumes), A2 (run time in `timing.txt`), A3 (`[solver]`
  section) are approved; section 11 lists as-built changes (frame times `(i + 1) / fps`, unit-normal
  averaging, seat names an emitter only, plain `output.name`, about 10 percent advection loss).
- Next session starts at slice 2: write its task plan from the outline in
  `docs/plans/2026-11-07-plume-slices.md` (multigrid pressure, vorticity confinement, curl-noise
  turbulence, wind and drag, the CFL substep cap, `extends` and `--set`), then build it. Its look review
  changes the puff, so the golden file is regenerated after that review.

## What Was Built

- **Recipe** (`src/plume/recipe/`): one schema of frozen dataclasses is the single source for keys, units,
  defaults and meanings; strict loading with "did you mean" errors; rules; preview coarsening; derived grid
  and timing; the resolved recipe written back as rerunnable TOML; `docs/recipe-reference.md` generated
  from the schema.
- **Simulation** (`src/plume/sim/`): dense MAC grid, clamped MacCormack advection with an RK2 backtrace,
  red-black Gauss-Seidel pressure with fixed sweeps, seeded value-noise emitters, ideal-gas buoyancy,
  dissipation, and a frame loop with a capture callback. Every kernel only gathers, for determinism.
- **Rendering** (`src/plume/render/`): orthographic camera from elevation and azimuth, a ray march giving
  heat, thickness and camera-space normals from blurred smoke.
- **Sheet** (`src/plume/sheet/`): union crop to a square with margin, bicubic resample, soften, quantize,
  pack, a 2 px gutter enforced by retry, and the sheet JSON contract.
- **Reports** (`src/plume/report/`): contact sheets on neutral and grass, the channel strip, `numbers.txt`,
  `timing.txt`.
- **CLI** (`src/plume/cli/`): `plume version`, `plume check`, `plume run` with `--preview`, `--device` and
  `--out`.
- **Docs**: design brief (D1 to D34), spec, slice plan, `CLAUDE.md`, `README.md`, `docs/look-tuning.md`.

## Key Decisions

- **Warp on Python, not a custom CUDA or C++ build.** One codebase runs on the 2080 Ti and on Linux CPU for
  cloud sessions; the exact pin guards the 2080 Ti being Warp's minimum GPU.
- **Keep 2D frame images, not volumes (A1).** Volumes at close-up size would need about 6 GB; frames
  rendered at 2 px per cell lose no detail.
- **Frame `i` shows `(i + 1) / fps`.** Frame 0 at time 0 would be empty.
- **The golden file comes from CUDA and the test runs on CPU.** It checks the approved look and the CPU
  path in one test, and CI can run it.
- **GitHub Actions instead of WSL for the Linux check.** WSL lacked uv; installing it was not asked for.

## What Went Wrong and What Changes

- **The plan's conservation bound was wrong for the method.** T1.7 asked for total smoke within 2 percent
  over 40 steps; the puff lost 16 percent at 400 K. Time went into hunting a solver leak (more pressure
  sweeps, plain semi-Lagrangian, a puff away from walls) before it proved to be the advection scheme
  itself, which is not conservative. -> **What changes:** when a plan sets a numeric bound on a numerical
  method (conservation, accuracy, convergence), measure the method on the smallest case first and set the
  bound from that measurement and the method's known behavior, saying why in the test. (promoted to
  memory [[measure-before-setting-solver-bounds]])
- **A recipe value reached a file path unchecked.** `output.name` with `../` could write outside the
  output folder; an automated security review caught it after `plume run` landed, and `69a9684` fixed it.
  -> **What changes:** when a recipe key becomes part of a file path, validate it as a plain name in
  `recipe/rules.py` at load time (as `check_output_name` does) and add a rejection test. (promoted to
  `CLAUDE.md`)
- **The golden file nearly came from a stale folder.** `out/smoke_puff/preview/numbers.txt` was left from
  an earlier recipe (fade `never`, `frame_m` 1.66) and would have locked in a look the user never saw.
  Rerunning the committed recipe into a fresh folder and diffing caught it. -> **What changes:** when
  storing or refreshing a golden file, generate it from a fresh run of the committed recipe; never copy
  from `out/`. (promoted to `CLAUDE.md`)
- **Preview smoke colors were guessed, costing extra tuning runs.** The first smoke color sat near
  mid-gray and vanished on the neutral sheet; the next read pink on grass. It settled only after sampling
  the Petri reference image (warm gray `#aea193`, ambient 0.65). -> **What changes:** when tuning `[look]`
  colors, sample them from the art reference image and check both contact sheets before showing the user.
  (promoted to `docs/look-tuning.md`)
- **A shared test helper first lived beside one test folder.** `tests/sim/grid_helpers.py` with a
  `pythonpath` of `tests/sim` had to move to `tests/support/`. -> (already in `CLAUDE.md`: shared test
  helpers live in `tests/support/`.)

## Recommended Backlog Items

- See [`idea-2026-11-07-rising-effects-fill-half-frames`](../backlog/idea-2026-11-07-rising-effects-fill-half-frames.md) - Rising effects fill only about half their frames
- See [`idea-2026-11-07-advection-loses-small-puff-smoke`](../backlog/idea-2026-11-07-advection-loses-small-puff-smoke.md) - Advection loses about 10 percent of a small puff's smoke
- See [`idea-2026-11-07-light-smoke-neutral-contact-sheet`](../backlog/idea-2026-11-07-light-smoke-neutral-contact-sheet.md) - Light smoke barely shows on the neutral contact sheet
- See [`feature-2026-11-07-seat-point-meters`](../backlog/feature-2026-11-07-seat-point-meters.md) - A seat given as a point in meters

## Files Most Touched

- `docs/specs/2026-11-07-plume-design.md` - the spec, amendments A1 to A3, as-built changes and run times.
- `docs/specs/2026-11-07-plume-design-brief.md` - the 34 settled design decisions and their sources.
- `src/plume/recipe/schema.py` - every recipe key, unit, default and meaning.
- `docs/plans/2026-11-07-plume-slices.md` - slice 1 tasks and slices 2 to 6 outlines.
- `docs/recipe-reference.md` - generated reference for every key.
- `src/plume/sim/emitters.py` - sphere and box emitters with seeded noise breakup.
- `src/plume/recipe/rules.py` - value checks, including the plain `output.name` rule.
- `src/plume/cli/run.py` - the run pipeline from recipe to the eight output files.
- `src/plume/report/numbers.py` - per-frame measurements, peak and fade frames.
- `src/plume/sim/pressure.py` - divergence, red-black sweeps and gradient subtraction.
