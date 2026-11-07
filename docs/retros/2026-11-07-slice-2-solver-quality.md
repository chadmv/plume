---
date: 2026-11-07
topic: slice-2-solver-quality
branch: claude/project-thread-cf8c5q
pull_request: 7
---

# Session Retro: 2026-11-07 - Slice 2, solver quality and iteration tools

**TL;DR:** Slice 2 gave Plume's smoke solver the tools it needs to look alive: a faster, more accurate
pressure solve, swirl-keeping and swirl-making forces, wind and drag, and an automatic step-size guard.
The agent can now also try a value with `--set` and build one recipe on another with `extends`. The
smoke puff now billows and tears into soft strands instead of rolling into a dome, and Chad approved it.
Along the way, the old "advection loses smoke" question turned out to be the reverse: advection was
quietly adding smoke, up to doubling it with turbulence. It no longer can.

## Handoff

- PR #7 on `claude/project-thread-cf8c5q`. Plan: `docs/plans/2026-11-07-slice-2-solver-quality.md`
  (T2.1 to T2.8). Spec section 13 records what was built.
- Tests: 115 pass, 2 skip (GPU) on CPU in the cloud session. **GPU not checked:** the `gpu` tests (CPU
  against CUDA, two CUDA runs give the same bytes) and GPU timing need a run on the 2080 Ti before merge.
- Golden: `tests/golden/smoke_puff_preview.numbers.txt` was refreshed after Chad's approval, from a fresh
  CPU preview of the committed recipe (byte-identical to the reviewed preview's numbers).
- The approved puff (full run, CPU): peak frame 5, fade frame 58 of 64, `frame_m` 1.39, seat (0.536,
  0.756), 203 steps (the CFL cap added 11).
- Timing, cloud CPU (4 cores): preview 40 s (192 steps since PR #6 matched preview and final step
  length), over the 30 s CPU budget; full sheet about 7 minutes. Multigrid alone cut the slice 1 preview
  from 11.7 s to 8.3 s at slice 1's step count.
- Next: slice 3 (combustion and the fireball plume), now unblocked.

## What Was Built

- **Variations** (`recipe/variation.py`): `extends` (relative `.toml` parents, deep-merged, chains, loops
  rejected) and `--set key=value` on `run` and `check`; `settings.toml` records both and reruns as is.
- **Multigrid pressure** (`sim/multigrid.py`), the default: cell-centered finite volumes that weigh cells
  overhanging an odd-sized axis, open-face zero pressure placed where the top grid has it, coarsest-level
  sweeps that grow with its longest axis.
- **Forces**: vorticity confinement scaled by cell size (`sim/vorticity.py`), curl-noise turbulence as a
  discrete curl, divergence-free on the grid (`sim/turbulence.py`), wind and drag (`sim/forces.py`).
- **CFL cap** (`sim/step_cap.py`, `sim/run.py`): per-frame step counts from the fastest face or emitter;
  bit-identical to slice 1 when it does not bind.
- **Smoke budget** (`sim/conserve.py`, `sim/reduce.py`): MacCormack's smoke total held between the plain
  semi-Lagrangian total and the total before the step.

## Key Decisions

- **Multigrid geometry over padding or semi-coarsening.** Weighing the overhanging coarse cells kept one
  `GridInfo` and fixed odd-sized grids (80 x 100 x 80 closed went from 0.78 to 0.1 per cycle).
- **Turbulence as a discrete curl at face edges.** Exactly divergence-free on the grid, so the projection
  leaves it alone, and the same in meters at any cell size (0.8 percent apart).
- **Wind acts through drag.** Wind without drag is a recipe error rather than a silent no-op.
- **Advection smoke: hold the total, do not budget outflow.** Bounds from totals the scheme itself makes
  (never above the start of the step, never below plain semi-Lagrangian) avoid estimating outflow.

## What Went Wrong and What Changes

- **The smoke-loss item measured the wrong case.** Slice 1 measured a tiny sharp puff and saw a loss;
  the real puff with open faces gained 30 percent, and 68 to 109 percent with turbulence. -> **What
  changes:** when settling a numerical question, measure the example recipe at preview and final cell
  sizes, not only the unit test's case. (Applies [[measure-before-setting-solver-bounds]].)
- **The first smoke budget drained smoke at open faces.** "Before minus estimated outflow" over-counted
  outflow (the cap allows over a cell per step at the top), and a hot puff in a short domain lost nearly
  all its smoke. The code-reviewer caught it with a short-against-tall domain probe, now a test. ->
  **What changes:** a correction that rescales a whole field gets a test where part of the field
  leaves the domain.
- **Turbulence tuning on previews hid full-size blowups.** Settings that looked fine at 48 cells ran away
  to 25 to 49 m/s at full size, because turbulence pushes all the air and confinement feeds on the spin.
  -> **What changes:** before showing a forces-heavy look, run it at full size once; `docs/look-tuning.md`
  says how to set drag. Backlog: [`idea-2026-11-07-turbulence-pushes-all-air`](../backlog/idea-2026-11-07-turbulence-pushes-all-air.md).
- **Force-push is blocked here.** A rebase after pushing could not be pushed; merging main worked. ->
  **What changes:** after the first push, bring in main with a merge.
- **The playbook's engineer split was not used.** The orchestrator built the tasks itself and used the
  code-reviewer (as general-purpose agents loading `.claude/agents/code-reviewer.md`, since this session
  could not load the agent types) after each group; the verifier gate was the full suite plus the
  same-bytes and golden tests run directly. Reviews found real bugs in every round (`--set extends`, tall
  domains, the outflow drain), so keep them.

## Recommended Backlog Items

- See [`idea-2026-11-07-turbulence-pushes-all-air`](../backlog/idea-2026-11-07-turbulence-pushes-all-air.md) - Turbulence pushes all the air, so it needs drag to stay bounded
- See [`idea-2026-11-07-cfl-cap-measures-at-frame-start`](../backlog/idea-2026-11-07-cfl-cap-measures-at-frame-start.md) - The CFL cap measures speed only at the start of each frame
- See [`bug-2026-11-07-nan-recipe-values-pass-rules`](../backlog/bug-2026-11-07-nan-recipe-values-pass-rules.md) - A nan recipe value passes the range rules
- The CPU preview is over its 30 s budget; [`feature-2026-11-07-preview-time-budget-guard-ci`](../backlog/feature-2026-11-07-preview-time-budget-guard-ci.md) and slice 6 cover it.

## Files Most Touched

- `src/plume/sim/multigrid.py`, `src/plume/sim/pressure.py` - the pressure solve.
- `src/plume/sim/turbulence.py`, `src/plume/sim/vorticity.py`, `src/plume/sim/forces.py` - forces.
- `src/plume/sim/run.py`, `src/plume/sim/step_cap.py`, `src/plume/sim/stepper.py` - time stepping.
- `src/plume/sim/conserve.py`, `src/plume/sim/reduce.py` - the smoke budget.
- `src/plume/recipe/variation.py`, `src/plume/recipe/load.py`, `src/plume/recipe/schema.py` - recipes.
- `docs/specs/2026-11-07-plume-design.md` section 13, `docs/look-tuning.md`.
