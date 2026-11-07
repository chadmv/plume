---
title: Advection loses about 10 percent of a small puff's smoke
type: idea
status: closed
created: 2026-11-07
closed: 2026-11-07
resolution: fixed
source: slice 1 retro, frame loop conservation test
---

# Advection loses about 10 percent of a small puff's smoke

## Summary
A mass-correction step (rescale smoke to emitted minus dissipated) or a conservative scheme would keep
density predictable while tuning; weigh it with slice 2's solver work.

## Context
Clamped MacCormack advection is not conservative: a small, sharp puff loses about 10 percent of its smoke
over 40 steps (plain semi-Lagrangian about 7) with almost no divergence left after projection, so it is
the scheme, not a leak. The frame loop test was relaxed to 320 K with a 15 percent bound because of it.

## Related
- `src/plume/sim/advect.py`, `src/plume/sim/stepper.py`
- `tests/sim/test_frame_loop.py`
- `docs/specs/2026-11-07-plume-design.md` section 11
- `docs/retros/2026-11-07-slice-1-smoke-puff.md`

## Notes
- 2026-11-07: the test comment in `tests/sim/test_frame_loop.py:34-35` now measures about 11 percent (plain
  semi-Lagrangian about 8) at the test's 320 K; the 10 and 7 above and in the spec are the earlier
  measurement. The 15 percent bound still holds.
- 2026-11-07 (slice 2, T2.6): settled by measuring the real puff instead of the small test case. With no
  dissipation and the recipe's open faces, clamped MacCormack *gained* smoke: 30 percent over 2.4 s for the
  plain puff, and with turbulence and confinement 68 percent on a 0.031 m grid against 109 percent on the
  0.052 m preview grid. Clamping the correction's dips at wispy edges adds smoke, more on coarse grids, so
  preview and final drifted apart. Fixed with a smoke budget (`src/plume/sim/conserve.py`): after each
  advection the field is scaled to the total before the step minus the upwind outflow through open faces.
  The same probes now hold the total to within 0.05 percent; the closed-box test bound went from 15
  percent to 1e-4.
