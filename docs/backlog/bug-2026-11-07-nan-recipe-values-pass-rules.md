---
title: A nan recipe value passes the range rules
type: bug
status: open
created: 2026-11-07
priority: low
source: slice 2 code review (T2.1)
---

# A nan recipe value passes the range rules

## Summary
`_at_least` and `_between` in `src/plume/recipe/rules.py` compare with `<`, which is False for `nan`, so
`nan` from a file or from `--set key=nan` passes and fails late inside the simulation. Reject non-finite
numbers when building the recipe.

## Related
- `src/plume/recipe/rules.py`, `src/plume/recipe/build.py`
- [[bug-2026-11-07-recipe-mistakes-pass-check-fail-late]]
