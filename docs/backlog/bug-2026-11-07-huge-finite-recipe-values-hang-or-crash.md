---
title: Huge finite recipe values hang a run or crash the TOML reader
type: bug
status: open
created: 2026-11-07
priority: low
source: code review of the recipe-check fix, 2026-11-07
---

# Huge finite recipe values hang a run or crash the TOML reader

## Summary
Finite but extreme values still pass `plume check` and fail late: a huge `time.warmup_s` makes
`round(warmup_s / dt)` warmup steps, and a tiny `domain.cell_m` makes `round(size / cell)` cells per axis,
so the run hangs or runs out of memory instead of exiting 2. Separately, `tomllib` raises a bare
`ValueError` (traceback, exit 1) for an integer literal over 4300 digits, in a recipe file or a `--set`
value, before any Plume code sees it.

## Proposal
Cap total steps and total cells at load time with a recipe error naming the key, and wrap the TOML
readers' `ValueError` as a `RecipeError`.

## Related
- `src/plume/recipe/derived.py`, `src/plume/recipe/variation.py` (`read_toml`, `_parse_value`)
- [[bug-2026-11-07-recipe-mistakes-pass-check-fail-late]]
