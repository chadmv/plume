---
title: Turbulence pushes all the air, so it needs drag to stay bounded
type: idea
status: open
created: 2026-11-07
source: slice 2 look tuning
---

# Turbulence pushes all the air, so it needs drag to stay bounded

## Summary
Curl-noise turbulence accelerates every cell, smoke or not, so without enough `forces.drag_per_s` the air
keeps speeding up; with vorticity confinement feeding on that spin, full-size runs reached 25 to 49 m/s
while previews looked fine. Consider weighting the push (and maybe confinement) by smoke or temperature, or
expressing strength as a target swirl speed, so a recipe cannot run away.

## Context
Slice 2 tuning: strength 0.2 to 0.4 m/s^2 with drag 0.2 to 0.3 and confinement 2 to 3 blew past
`solver.max_substeps` at full size; drag 0.5 held. The fastest swirl settles near a few times
`strength_mps2 / drag_per_s` (the push peaks at about 3.4 times the strength). Drag also slows the puff's
rise, which the approved puff shows.

## Related
- `src/plume/sim/turbulence.py`, `src/plume/sim/vorticity.py`, `docs/look-tuning.md`
