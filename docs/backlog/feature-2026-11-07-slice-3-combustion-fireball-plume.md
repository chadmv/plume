---
title: Slice 3 - combustion and the fireball plume
type: feature
status: open
created: 2026-11-07
priority: high
source: build plan docs/plans/2026-11-07-plume-slices.md, slice 3 outline
parent: feature-2026-11-07-plume-first-version
blocked_by: [feature-2026-11-07-slice-2-solver-quality-iteration-tools]
---

# Slice 3 - combustion and the fireball plume

## Summary
Add the fuel model so Plume makes fire, not only smoke: fuel and flame fields, ignition, burn rate, heat
and smoke per fuel, and expansion as a divergence source, with flame showing in the heat channel. This is
the first effect Petri asked for (a fireball's flame plume turning to smoke).

## Proposal
- [ ] Fuel and flame fields; ignition temperature, burn rate, heat and smoke released per fuel (D8)
- [ ] Expansion as a divergence source in the pressure solve
- [ ] R as a recipe-weighted blend of flame and the hot part of temperature (D8, D13)
- [ ] `[combustion]` section in the schema; reference regenerated
- [ ] `recipes/fireball_plume.toml`, emission ramp colors sampled from the art reference
- [ ] Look review against Petri's `docs/art-direction/reference/fireball-impact-meadow.png`; golden file

## Acceptance / Done When
- The user approves the fireball plume against the reference.
- A golden `numbers.txt` for the new recipe; a retro.

## Related
- `docs/plans/2026-11-07-plume-slices.md` (Slice 3)
- `docs/specs/2026-11-07-plume-design-brief.md` D8, D13
