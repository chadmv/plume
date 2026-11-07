---
title: Slice 6 - 512 px close-ups and performance
type: feature
status: open
created: 2026-11-07
priority: medium
source: build plan docs/plans/2026-11-07-plume-slices.md, slice 6 outline
parent: feature-2026-11-07-plume-first-version
blocked_by: [feature-2026-11-07-slice-5-looping-sheets]
---

# Slice 6 - 512 px close-ups and performance

## Summary
Support 512 px frames on 4096 px sheets for close-ups (grids up to about 256 x 384 x 256), profile the
pipeline, and meet and record the 60 s default-run budget on the 2080 Ti.

## Proposal
- [ ] 512 px frames on 4096 sheets; memory checked against amendment A1 (about 500 MB of frame images)
- [ ] Profile simulation, render and sheet stages; fix the hot spots
- [ ] Default run (about 128 cubed, 64 frames, 256 px) under 60 s on the 2080 Ti, recorded in the spec

## Acceptance / Done When
- The budget is met and recorded; a close-up recipe renders correctly; retro.

## Related
- `docs/plans/2026-11-07-plume-slices.md` (Slice 6)
- `docs/specs/2026-11-07-plume-design.md` sections 9, 10 (A1), 12
