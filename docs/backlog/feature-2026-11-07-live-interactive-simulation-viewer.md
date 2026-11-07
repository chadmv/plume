---
title: A live viewer app with an MCP server for interactive, chat-driven tuning
type: feature
status: open
created: 2026-11-07
priority: low
source: user request, 2026-11-07
---

# A live viewer app with an MCP server for interactive, chat-driven tuning

## Summary
An application that keeps a simulation running and renders it live, with an MCP server so the user can chat
with Claude to change recipe values and watch the effect update in real time. Today the loop is
edit, rerun, read the contact sheets; a live view would make look tuning a conversation instead of a
series of batch runs.

## Context
The brief makes Plume headless and command-line only for the first version ("Headless and command-line
only; no window", brief Constraints confirmed), so this is work for after the first version and needs its
own design: it changes that constraint.

## Proposal
Not a design, only the shape to explore:
- A long-running process that holds the grid on the GPU and re-simulates (or resumes) when a value
  changes, rendering frames with the existing ray march at preview resolution.
- An MCP server exposing tools such as set a recipe value (the same keys as `--set`), restart, step,
  read the numbers, save the recipe, and write the final sheet with the normal `plume run` path.
- A window or browser view showing the live render on the neutral and grass backgrounds, the channels,
  and the per-frame numbers.
- Determinism stays a property of `plume run`; the live view is for tuning, and the sheet still comes
  from a batch run of the saved recipe.

## Acceptance / Done When
- From a chat, the user changes a recipe value and sees the simulation re-render within a few seconds.
- The tuned recipe can be saved and produces the same look through `plume run`.

## Related
- `docs/specs/2026-11-07-plume-design-brief.md` (Intent; Constraints confirmed)
- [[feature-2026-11-07-slice-2-solver-quality-iteration-tools]] (`--set` and `extends`, the same key paths)
- [[feature-2026-11-07-plume-first-version]]
