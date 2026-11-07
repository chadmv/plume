---
title: A seat given as a point in meters
type: feature
status: open
created: 2026-11-07
source: slice 1 retro, spec section 11
---

# A seat given as a point in meters

## Summary
The seat can only name an emitter (spec section 11); effects whose anchor is not an emitter center (an
impact point on the ground) will need a point.

## Context
`camera.seat` defaults to the first emitter's name and the sheet JSON reports that emitter's center as
fractions of the frame. Slice 4's impact dust skirt is the first effect likely to need a ground point.

## Related
- `src/plume/recipe/schema.py` (`CameraSettings.seat`), `src/plume/recipe/rules.py`, `src/plume/cli/run.py`
- `docs/specs/2026-11-07-plume-design.md` section 11
- `docs/retros/2026-11-07-slice-1-smoke-puff.md`
