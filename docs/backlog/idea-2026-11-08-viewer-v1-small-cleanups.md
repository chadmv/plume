---
title: Small viewer cleanups left from the V1 Watch reviews
type: idea
status: open
created: 2026-11-08
priority: low
source: code reviews of slice V1 Watch, 2026-11-08
---

# Small viewer cleanups left from the V1 Watch reviews

## Summary
Low findings from the V1 Watch reviews that were not worth their own change in that slice:
- `view/viewport.py`: `Viewport` builds a whole `FrameRenderer`, which allocates a sheet-size raw image it never
  uses and a second light volume beside the live run's (a few MB of device memory per run at the puff's grid).
  A renderer that takes no domain view, or one shared with the live run once the run is done, would drop both.
- `view/app.py`: the Full or Preview toggle can change `derived.size_m` through rounding, which rebuilds the
  navigation and re-homes the camera; keeping the pose when the domain only moves by a cell would be kinder.
- `ruff check` reports about 74 findings across the repository (mostly import order; the `float(0.0)` UP018
  hits in Warp kernels are false positives Warp needs). Ruff is not in CI, so nothing keeps the style; either
  configure it (with the Warp exception) and add it to CI, or drop it.

## Related
- [[feature-2026-11-07-live-interactive-simulation-viewer]]
