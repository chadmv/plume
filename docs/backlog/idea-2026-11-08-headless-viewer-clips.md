---
title: Headless viewer clips from the command line
type: idea
status: open
created: 2026-11-08
priority: low
source: deferred from the live viewer design interview, 2026-11-08
---

# Headless viewer clips from the command line

## Summary
`plume view RECIPE --clip` (camera pose, view and frames as flags or a `.toml` from a saved clip) writes the same
animated PNG the viewer's Save clip does, with no window, so a cloud session or a script can look at a run in
motion and from other angles. Deferred by the live viewer design (`docs/specs/2026-11-08-live-viewer-design.md`,
V15): on the cloud CPU a full run of the smoke puff takes about 10 minutes, so it would mostly serve previews.

## Related
- [[feature-2026-11-07-live-interactive-simulation-viewer]]
- [[idea-2026-11-08-viewer-mcp-server]]
