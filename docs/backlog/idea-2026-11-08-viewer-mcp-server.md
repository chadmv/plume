---
title: An MCP server for the live viewer
type: idea
status: open
created: 2026-11-08
priority: low
source: deferred from the live viewer design interview, 2026-11-08
---

# An MCP server for the live viewer

## Summary
Tools a chat can call on a running `plume view`: set a recipe value, restart, step, jump to a frame, read the
numbers, save a still, save the recipe. The live viewer design (`docs/specs/2026-11-08-live-viewer-design.md`, V1)
left it out: the viewer follows the recipe file, so a chat already drives it by editing the recipe.

## Context
Worth building only if file editing proves too slow or too blunt in practice, for example when a chat needs to
read the viewer's state (current frame, camera) or ask for a still at an angle without the user.

## Related
- [[feature-2026-11-07-live-interactive-simulation-viewer]]
- [[idea-2026-11-08-headless-viewer-clips]]
