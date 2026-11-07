---
title: Preview time steps are four times longer than the final run's
type: bug
status: closed
created: 2026-11-07
priority: high
source: deep roadmap gaps review, 2026-11-07
closed: 2026-11-07
resolution: fixed
---

# Preview time steps are four times longer than the final run's

## Summary
The step is `1 / (fps * substeps)` and preview cuts frames from 64 to 16 without adding substeps, so
preview steps are four times longer (smoke puff: 0.05 s against 0.0125 s). Emitter temperature and velocity
blend by coverage once per step, not per second, so preview and final drift, against D30's promise that a
preview is a coarse version of the final look.

## Repro / Symptoms
Same 48-cell grid on CPU, 16 frames against 64: peak frame 1 of 16 against 5 of 64, `frame_m` 1.49 against
1.55, late-frame total thickness about 20 percent lower in the 16-frame run.

## Proposal
Keep the step length in seconds the same between preview and final (more substeps per preview frame), and
make emitter blending a rate per second. Fold into slice 2, whose CFL cap also changes step counts.

## Related
- `src/plume/recipe/derived.py:29`, `src/plume/recipe/load.py:40`, `src/plume/sim/emitters.py:86`, `:104`
- [[feature-2026-11-07-slice-2-solver-quality-iteration-tools]]

## Resolution
`--preview` now sets `substeps = ceil(frames * substeps / preview.frames)` (`recipe/load.py`,
`preview_substeps`), so the smoke puff preview takes 12 steps per frame of 0.0125 s, the full run's step.
Emitter temperature and velocity blend by `1 - (1 - coverage) ** (dt / (1/80 s))` (`sim/emitters.py`,
`blend_factor`), a rate per second that leaves the full smoke puff unchanged to within float rounding (its step is 1/80 s) and holds
when slice 2's CFL cap changes step counts.

Check on CPU at the 48-cell grid: the 16-frame preview matches every fourth frame of a 64-frame run at the
same times, all 16 frames, once both are scaled to one camera framing (the 64-frame run frames 1.547 m
against 1.491 m because it sees more frames; that scales coverage and thickness by 7.7 percent). Before
the fix the late frames were about 20 percent thinner. The cost: the preview simulates four times as many
steps (CPU preview in a cloud session went from 15 s to 44 s).

