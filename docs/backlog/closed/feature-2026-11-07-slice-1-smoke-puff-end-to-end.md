---
title: Slice 1 - buoyant smoke puff, end to end
type: feature
status: closed
created: 2026-11-07
priority: high
source: build plan docs/plans/2026-11-07-plume-slices.md, slice 1
parent: feature-2026-11-07-plume-first-version
closed: 2026-11-07
resolution: fixed
---

# Slice 1 - buoyant smoke puff, end to end

## Summary
A recipe for a rising puff of smoke becomes a finished sheet, contact sheets, channel strip and
per-frame numbers, on CPU and GPU, with `--preview`, determinism and Gauss-Seidel pressure (plan tasks
T1.1 to T1.14).

## Acceptance / Done When
- The spec's slice 1 success criteria (section 9) hold.

## Related
- `docs/plans/2026-11-07-plume-slices.md` (Slice 1)
- `docs/retros/2026-11-07-slice-1-smoke-puff.md`

## Resolution
Built and approved by the user on 2026-11-07; landed on `main` through pull request #1 (commits `4c93ccc`
to `8fb5969`). The approved puff's numbers are the golden file `tests/golden/smoke_puff_preview.numbers.txt`.
Filed after the fact so the umbrella's progress counts it.
