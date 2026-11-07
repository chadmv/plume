---
title: Log the ratio of rendered crop pixels to frame pixels
type: idea
status: open
created: 2026-11-07
source: deep roadmap gaps review, 2026-11-07
---

# Log the ratio of rendered crop pixels to frame pixels

## Summary
The domain view renders at 2 px per cell, so the smoke puff's crop is about 123 rendered px stretched up
to 256 px (preview: about 57 px to 128). Amendment A1 replaced D15's render-at-twice-and-average-down, but
nothing logs or checks the ratio, which matters for slice 6's 512 px close-ups.

## Proposal
Report the ratio in `numbers.txt` or the run summary, and warn (or raise `px_per_cell`) when frames are
upscaled by more than a set factor.

## Related
- `src/plume/render/camera.py:60`, `src/plume/sheet/resample.py:23`
- `docs/specs/2026-11-07-plume-design.md:88` (A1) against brief D15
- [[feature-2026-11-07-slice-6-close-ups-performance]]
