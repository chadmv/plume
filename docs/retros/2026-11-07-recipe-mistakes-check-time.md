---
date: 2026-11-07
topic: recipe-mistakes-check-time
branch: claude/project-thread-8mu9f1
---

# Session Retro: 2026-11-07 - Catch recipe mistakes at check time

**TL;DR:** Bad recipes that used to pass `plume check` and then fail mid-run (or silently) now stop at
load time with exit 2: nan and inf values, emitters that lie wholly outside the domain, seeds past
2^31 - 1, and a duration too small for its frames. Command-line usage mistakes (an unknown flag, a missing
argument) now exit 64, so an agent can tell them apart from a recipe error. No look change: the golden
preview still matches.

## Handoff

- Branch `claude/project-thread-8mu9f1`. Closes `bug-2026-11-07-recipe-mistakes-pass-check-fail-late`
  and `bug-2026-11-07-nan-recipe-values-pass-rules`.
- Tests: 138 pass, 2 skip (GPU) on CPU in the cloud session. Same-bytes CPU preview check passes (the
  sheet JSON differs only by its `--out` path in `written_by`, the known open bug). GPU not checked.
- The noise hash now adds its lattice offset to the seed unsigned (`sim/noise.py`). That gives the same
  values for every seed that did not overflow before, so outputs are unchanged; the CUDA same-bytes and
  CPU-against-CUDA tests should still be run on the PC.

## What Was Built

- `recipe/build.py`: `_number` rejects non-finite values, including a whole number too large for a float.
- `recipe/rules.py`: seed range (`SEED_MAX` in `schema.py`), emitter-reaches-domain rule, and a guard on a
  duration too small for its frames.
- `cli/main.py`: `EXIT_USAGE = 64` (the BSD `EX_USAGE` code) through an argparse subclass.
- README exit-code table; agent rules name the new code.

## Key Decisions

- The emitter rule tests the shape's reach, not its center. The first version tested the center, and the
  review showed it refused a ground source sunk below the floor that ran fine before.
- The domain bound is the requested `domain.size_m`, not the cell-rounded grid, so the rule is the same
  for preview and full runs; a shape that only grazes a face can still miss every cell.
- 64 over 3 for usage errors: it is the conventional code, and it is far from the run's own codes.

## What Went Wrong and What Changes

- The backlog item said "an emitter centered outside the domain", and I wrote that rule literally. The
  real failure is an emitter that emits nothing. Lesson: write the rule for the failure, not for the
  repro's wording.

## Recommended Backlog Items

- Filed: `bug-2026-11-07-huge-finite-recipe-values-hang-or-crash` (huge warmup or tiny cells hang a run;
  a 4300-digit integer crashes the TOML reader).

## Files Most Touched

`src/plume/recipe/{build,rules,schema}.py`, `src/plume/cli/main.py`, `src/plume/sim/noise.py`,
`tests/recipe/test_load.py`, `tests/cli/test_check.py`, `README.md`.
