---
title: Tests for box emitters, noise breakup, warmup and open-face outflow
type: feature
status: open
created: 2026-11-07
priority: medium
source: deep roadmap gaps review, 2026-11-07
---

# Tests for box emitters, noise breakup, warmup and open-face outflow

## Summary
Behavior later slices depend on has no tests: emitter tests cover spheres only, noise is tested only for
same-seed equality (not that it breaks the shape up at `scale_m`), `warmup_s` is never exercised, and no
test shows smoke leaving through an open face.

## Acceptance / Done When
- CPU tests at tiny grids for a box emitter's extent, breakup at `scale_m`, `warmup_s` rounded to whole
  steps, and smoke leaving through an open face.

## Related
- `tests/sim/test_emitters.py`, `tests/sim/test_pressure.py:38-44`, `src/plume/recipe/derived.py:36`
- Brief D10, D22, D24, D32
