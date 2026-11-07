---
title: Advection loses about 10 percent of a small puff's smoke
type: idea
status: open
created: 2026-11-07
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
