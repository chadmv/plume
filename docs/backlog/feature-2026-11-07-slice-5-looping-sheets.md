---
title: Slice 5 - looping sheets
type: feature
status: open
created: 2026-11-07
priority: medium
source: build plan docs/plans/2026-11-07-plume-slices.md, slice 5 outline
parent: feature-2026-11-07-plume-first-version
blocked_by: [feature-2026-11-07-slice-4-burst-emitters-ground-dust]
---

# Slice 5 - looping sheets

## Summary
Sheets that loop seamlessly for steady effects: run to a steady state, capture a span, and crossfade its
last frames into its first, so Petri can play a building fire and chimney smoke forever.

## Proposal
- [ ] `loop = true` and `loop_blend_frames = 8`: steady state, capture, crossfade (D26)
- [ ] Decide how the union crop, peak and fade numbers read for a loop
- [ ] `recipes/building_fire.toml` and `recipes/chimney_smoke.toml`; look reviews; golden files

## Acceptance / Done When
- Both recipes loop without a visible seam and pass the user's look review; golden files; retro.

## Related
- `docs/plans/2026-11-07-plume-slices.md` (Slice 5)
- `docs/specs/2026-11-07-plume-design-brief.md` D26
