---
title: source becomes an absolute path outside a git checkout
type: bug
status: open
created: 2026-11-07
priority: medium
source: deep roadmap gaps review, 2026-11-07
---

# source becomes an absolute path outside a git checkout

## Summary
With no `.git` above the recipe, `source_path` falls back to the path as given, so `source` in the sheet
JSON and `numbers.txt` can hold a machine-local absolute path, and the golden test fails on a `git archive`
copy. This breaks the standalone rule in `CLAUDE.md`.

## Repro / Symptoms
From a copy of the repo with no `.git`, the golden test fails with
`'/tmp/.../recipes/smoke_puff.toml' != 'recipes/smoke_puff.toml'`.

## Acceptance / Done When
- `source` is never absolute: relative to the git root when there is one, otherwise a documented fallback
  (for example the recipe's file name or a path relative to the working folder).
- The golden test passes outside a git checkout.

## Related
- `src/plume/sheet/sheet_json.py:245-251`, `tests/cli/test_golden_numbers.py:81-85`, `:100`, `:110-111`
- [[bug-2026-11-07-written-by-machine-local-paths]]
