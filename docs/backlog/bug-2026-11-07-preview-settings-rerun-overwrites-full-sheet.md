---
title: Rerunning a preview's settings.toml overwrites the full sheet
type: bug
status: open
created: 2026-11-07
priority: medium
source: deep roadmap gaps review, 2026-11-07
---

# Rerunning a preview's settings.toml overwrites the full sheet

## Summary
`settings.toml` stores the resolved `output.name` but not that the run was a preview or which recipe it
came from, so `plume run out/<name>/preview/settings.toml` writes a 16-frame, 128 px sheet into the full-run
folder `out/<name>/`, replacing the full sheet, and its JSON `source` becomes the settings file.

## Acceptance / Done When
- Rerunning a preview's `settings.toml` reproduces the preview into the preview folder (or refuses with a
  clear error), and never overwrites the full sheet.
- `source` still names the original recipe.

## Related
- `src/plume/recipe/load.py:59`, `src/plume/cli/run.py:87-91`, `src/plume/recipe/serialize.py:82-93`
- Brief D28 (`settings.toml` is itself rerunnable)
