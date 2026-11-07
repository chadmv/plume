---
title: Plume's first version, slices 1 to 6
type: feature
status: open
created: 2026-11-07
priority: high
source: build plan docs/plans/2026-11-07-plume-slices.md, brief D34
---

# Plume's first version, slices 1 to 6

## Summary
The umbrella for the six slices of the build plan (D34): everything Petri needs from Plume's first
version, from the smoke puff through combustion, bursts with ground dust, looping sheets, and 512 px
close-ups with the 60 s run budget. Each slice is its own child item, plan, pull request, look review and
retro.

## Context
The plan (`docs/plans/2026-11-07-plume-slices.md`) details slice 1 task by task and outlines slices 2 to
6; each later slice writes its own task plan when it starts. Slices run in the D34 order because each
builds on the one before (solver quality before combustion, combustion before the fireball impact and the
building fire, all features before the performance pass).

## Acceptance / Done When
- The spec's whole-first-version success criteria (section 9) hold: a default run (about 128 cubed, 64
  frames, 256 px) finishes in under 60 s on the 2080 Ti, and the fireball plume, impact dust, building
  fire and chimney smoke recipes each pass the user's look review against the reference.
- Every slice child is closed.

## Related
- `docs/plans/2026-11-07-plume-slices.md`
- `docs/specs/2026-11-07-plume-design.md` section 9
- `docs/specs/2026-11-07-plume-design-brief.md` D34
