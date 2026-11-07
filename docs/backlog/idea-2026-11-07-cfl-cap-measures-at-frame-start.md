---
title: The CFL cap measures speed only at the start of each frame
type: idea
status: open
created: 2026-11-07
source: slice 2 code reviews (T2.5, T2.6)
---

# The CFL cap measures speed only at the start of each frame

## Summary
Speed gained during a frame (buoyancy, turbulence, confinement, the projection) is caught only at the next
frame, so a step can cross more than `solver.max_cells_per_step` cells. A review measured 2.2 cells per
step at an open top. Re-planning partway through a block, or adding a margin from the forces' size, would
make the cap a true bound. The step count also jumps by whole numbers, so CPU and CUDA could choose
different counts near a boundary; watch the `gpu` tolerance test.

## Related
- `src/plume/sim/step_cap.py`, `src/plume/sim/run.py`, `tests/sim/test_step_cap.py`
