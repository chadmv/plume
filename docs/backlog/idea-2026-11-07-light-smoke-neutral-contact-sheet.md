---
title: Light smoke barely shows on the neutral contact sheet
type: idea
status: open
created: 2026-11-07
source: slice 1 retro, smoke puff look review
---

# Light smoke barely shows on the neutral contact sheet

## Summary
The `#808080` background is close to the warm-gray smoke; a darker neutral or a checker would make that
sheet useful for smoke.

## Context
The smoke puff is judged on `contact_grass.png` for now; `docs/look-tuning.md` (Density and color) says
so. The neutral sheet exists to judge an effect away from Petri's grass.

## Related
- `src/plume/recipe/schema.py` (`BackgroundSettings.neutral`), `src/plume/report/contact.py`
- `docs/retros/2026-11-07-slice-1-smoke-puff.md`
