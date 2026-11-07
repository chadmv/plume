---
title: Guard the preview time budget in CI
type: feature
status: open
created: 2026-11-07
priority: low
source: deep roadmap gaps review, 2026-11-07
---

# Guard the preview time budget in CI

## Summary
The 10 s GPU and 30 s CPU preview targets were measured by hand once. CI runs the CPU preview but never
reads `timing.txt`, so a slowdown from slice 2's new kernels would go unnoticed until slice 6.

## Proposal
Upload `timing.txt` as a build artifact and fail on a loose bound (well above the 30 s CPU target, since
runners vary).

## Related
- `.github/workflows/ci.yml:19-20`, `src/plume/report/timing.py`
- `docs/specs/2026-11-07-plume-design.md` sections 9 and 11
