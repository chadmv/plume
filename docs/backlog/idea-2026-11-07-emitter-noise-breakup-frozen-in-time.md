---
title: Emitter noise breakup is frozen in time
type: idea
status: open
created: 2026-11-07
source: deep roadmap gaps review, 2026-11-07
---

# Emitter noise breakup is frozen in time

## Summary
The breakup samples `value_noise(seed, stream, x / scale_m)` with no time input, so a long-running emitter
shows the same pattern every step; the fire and smoke columns of slices 3 and 5 will get fixed streaks. The
noise stream is the emitter's index, so reordering emitters (or `extends` merging lists) changes the
pattern.

## Proposal
Add a time (or scroll speed) input to the breakup noise, and derive the stream from the emitter's name
rather than its index.

## Related
- `src/plume/sim/emitters.py:59`, `:125` (`p.stream = index`), `src/plume/sim/noise.py`
- [[feature-2026-11-07-slice-3-combustion-fireball-plume]], [[feature-2026-11-07-slice-5-looping-sheets]]
