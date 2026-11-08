---
title: Cut the light volume's cost on CPU full runs
type: idea
status: open
created: 2026-11-08
source: shade channel layout build, full smoke puff run on cloud CPU
---

# Cut the light volume's cost on CPU full runs

## Summary
The shade layout marches every cell toward the light every frame (half-cell steps to the domain's edge).
On the cloud CPU (4 cores) the full smoke puff (80 x 100 x 80 cells, 64 frames) spent 160.6 s rendering,
out of 578 s in all (the normal layout's full-run render was not measured); the code review measured the
light volume alone at about 0.9 s per full-size frame. The preview's render rose from 1.1 s (normal
layout) to 3.1 s, small beside its 44 s of simulation. On the PC's GPU the full run's render is 0.16 s
(0.27 s in the normal layout), so this matters only for CPU runs.

## Proposal
Only if CPU full runs become routine, consider
marching only cells whose trilinear neighborhood holds smoke (the camera march gives empty cells no
weight), a coarser light grid, or stopping a march once the light is below a byte's worth. Each keeps the
gather-only and fixed-count rules; the last changes bytes, so it needs the user's look check.

## Related
- `src/plume/render/light_volume.py`
- `docs/specs/2026-11-07-shade-channel-design.md` section 3
- [[feature-2026-11-07-slice-6-close-ups-performance]]
