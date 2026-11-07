---
title: Recipe mistakes pass plume check and fail late
type: bug
status: open
created: 2026-11-07
priority: medium
source: deep roadmap gaps review, 2026-11-07
---

# Recipe mistakes pass plume check and fail late

## Summary
Some bad recipes pass `plume check` and then fail during the run with exit 1 or a traceback, so the agent
loses a run and cannot tell a recipe error from a crash. Strict, early errors with exit 2 are what D20 and
D27 promise.

## Repro / Symptoms
- `smoke_per_s = nan` passes check; `plume run` exits 1 with "no frame shows any smoke".
- `duration_s = inf` crashes with a ZeroDivisionError traceback.
- An emitter centered outside the domain passes check, then exits 1 at run time.
- A seed of 2^32 or more is silently cut to 32 bits (seeds 5000000000 and 705032704 give identical noise).
- An argparse usage error (an unknown flag) also exits 2, the same code as a recipe error.

## Acceptance / Done When
- Non-finite numbers, emitters outside the domain and out-of-range seeds are recipe errors at load time
  (exit 2, with a test each).
- Usage errors exit with a code distinct from recipe errors, documented in the README.

## Related
- `src/plume/recipe/build.py:66-69`, `src/plume/recipe/rules.py:48-69`, `src/plume/recipe/derived.py:28-29`
- `src/plume/sim/noise.py:27`, `src/plume/cli/main.py:21`, `:36-40`
