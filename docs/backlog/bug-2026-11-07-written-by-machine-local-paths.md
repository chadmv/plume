---
title: written_by carries machine-local paths and drops quoting
type: bug
status: open
created: 2026-11-07
priority: medium
source: deep roadmap gaps review, 2026-11-07
---

# written_by carries machine-local paths and drops quoting

## Summary
`written_by` is `" ".join(["plume", *argv])`, so an argument with a space no longer reproduces the command,
and Petri recipes (which live outside Plume) put home-folder or drive-letter paths into the sheet JSON that
Petri commits. The brief rejected absolute `source` paths for the same reason.

## Proposal
Use `shlex.join`, and write recipe and `--out` paths relative to the recipe's repository.

## Acceptance / Done When
- `written_by` round-trips through a shell for arguments with spaces.
- No absolute path appears in `written_by` for a recipe inside a git repository.

## Related
- `src/plume/cli/main.py:34`
- [[bug-2026-11-07-source-path-absolute-outside-git]]
