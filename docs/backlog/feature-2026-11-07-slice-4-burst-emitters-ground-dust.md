---
title: Slice 4 - keyframed and burst emitters, ground dust
type: feature
status: open
created: 2026-11-07
priority: medium
source: build plan docs/plans/2026-11-07-plume-slices.md, slice 4 outline
parent: feature-2026-11-07-plume-first-version
blocked_by: [feature-2026-11-07-slice-3-combustion-fireball-plume]
---

# Slice 4 - keyframed and burst emitters, ground dust

## Summary
Let emitters change over time and burst outward, and make dust roll along the closed floor, so Plume can
make the fireball impact with its low dust skirt from the reference image.

## Proposal
- [ ] Keyframes on any numeric emitter value, `[[time_s, value], ...]`, linear (D22)
- [ ] `velocity_mode = "outward"` tuned for bursts (D22)
- [ ] The impact dust skirt rolling along the closed floor (D24)
- [ ] A seat at a ground point, likely needed for the impact (see the related item)
- [ ] `recipes/fireball_impact_dust.toml`; look review; golden file

## Acceptance / Done When
- The user approves the impact dust recipe against the reference; golden file; retro.

## Related
- `docs/plans/2026-11-07-plume-slices.md` (Slice 4)
- [[feature-2026-11-07-seat-point-meters]]
- `src/plume/sim/emitters.py`, `src/plume/recipe/schema.py`
