---
title: Small cleanups left from the viewer's slice V3
type: idea
status: open
created: 2026-11-09
priority: low
source: whole-slice review of viewer slice V3 Inspect, 2026-11-09
---

# Small cleanups left from the viewer's slice V3

## Summary
Review findings judged too small to hold the slice:
- **Slice legend range on the host.** `SliceDrawer.prepare` copies the whole prepared field to the host
  (`values.numpy()`, about 2.5 MB a frame at the smoke puff's grid) only to find the legend's range. A device
  reduction would avoid it; not measured, so check the redraw time on the PC with the slice on first.
- **A Volume clip from a thinned cache plays fast.** One image per kept frame at `1 / fps`, so a cache keeping
  every second frame gives a clip twice the effect's speed. Either hold each image for `stride / fps` or note
  the stride in the clip's `.toml`.
- **Edge-mark test.** `tests/view/test_live_run.py` checks every landed frame has an edge entry, not that a puff
  rising into an open top is marked; a run that reaches the ceiling would pin the threshold and field.
- **`app.py` size** (about 630 lines): the stills and clips (`_save_still`, `_save_clip`, `_capture_info`) and
  the slice legend could move out.

## Related
- [[feature-2026-11-07-live-interactive-simulation-viewer]]
