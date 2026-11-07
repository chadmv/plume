---
title: Rising effects fill only about half their frames
type: idea
status: open
created: 2026-11-07
source: slice 1 retro, smoke puff look review
---

# Rising effects fill only about half their frames

## Summary
The crop is the union of every frame's bounds, so a puff that climbs makes every frame cover the whole
climb. A crop that follows the seat, or a higher fringe threshold for the crop, would give traveling
effects more pixels; deciding it means revisiting the union-crop rule in the sheet contract.

## Context
The approved smoke puff fills about 40 to 50 percent of its frame width. `docs/look-tuning.md` (Framing)
lists the recipe-side workaround: less travel.

## Related
- `src/plume/sheet/crop.py` (`content_box`, `square_crop`), `src/plume/sheet/assemble.py`
- `docs/specs/2026-11-07-plume-design.md` section 5 (sheet assembly)
- `docs/retros/2026-11-07-slice-1-smoke-puff.md`
