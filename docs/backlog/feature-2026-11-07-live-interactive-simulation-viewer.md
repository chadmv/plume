---
title: A live viewer app for judging and tuning simulations
type: feature
status: open
created: 2026-11-07
priority: high
source: user request, 2026-11-07
---

# A live viewer app for judging and tuning simulations

## Summary
**Slice V1 Watch built 2026-11-08:** plan `docs/plans/2026-11-08-viewer-v1-watch.md`; `plume view RECIPE`
watches a run live from any angle and re-runs on save. **Slice V2 Tune built 2026-11-09:** plan
`docs/plans/2026-11-09-viewer-v2-tune.md`; stages on every recipe table, the editing panel, Save with tomlkit,
Compare and Split, the light arrow drag. **Slice V3 Inspect built 2026-11-09:** plan
`docs/plans/2026-11-09-viewer-v3-inspect.md`; the Sheet tab and `plume view OUT_DIR`, the numbers strip, the
slice plane (velocity in the frame cache), clips and stills. The item closes once the user has judged a sheet
in the Sheet tab and a thread has read back a clip the user saved (spec section 10).

**Designed 2026-11-08:** `docs/specs/2026-11-08-live-viewer-design.md` (decisions V1 to V18, amendment A5),
built in three slices, V1 Watch, V2 Tune and V3 Inspect (its section 10). The user's reason (2026-11-08): "it
needs an application to view the live simulation in order to properly judge the simulation results. Just
judging the sheets is not enough." The MCP server below was deferred to
[[idea-2026-11-08-viewer-mcp-server]]; a chat drives the viewer by editing the recipe file, which it follows.

Original summary: An application that keeps a simulation running and renders it live, with an MCP server so the user can chat
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
