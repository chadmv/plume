---
title: Selectable channel layout with a baked self-shadowed shade
type: feature
status: closed
closed: 2026-11-08
resolution: fixed
created: 2026-11-07
priority: high
source: check of Plume against its first consumer's flipbook needs (Petri changed B to a baked shade after a fireball look review)
---

# Selectable channel layout with a baked self-shadowed shade

## Summary
Let a recipe choose the sheet's B and A channels: a baked, self-shadowed shade with A unused (the new
default) or today's camera-space normal x and y. A game then gets dense, self-shadowed smoke from one
multiply. Land it before slice 3, whose fireball plume is the first sheet a game will use.

## Context
Plume writes `heat,thickness,normal_x,normal_y`. Its first consumer, Petri, moved to
`heat,thickness,shade,unused` in its fireball look rounds and its sheet check now rejects any other
layout, so a Plume sheet today would not load there. Both layouts are general; Plume stays uncoupled from
any game.

## Proposal
- [ ] `output.channels` (two valid layouts), `render.light_dir` (replaces `look.sun_dir`), `render.shade_fill`,
      `render.shade_fade_thickness`, `render.shade_neighborhood_px`, `look.shade_depth`; reference regenerated
- [ ] Light-transmittance volume kernel (gather toward the light) and the shade sum in the camera march
- [ ] Thin-pixel easing, shade normalization (`shade_divisor`), quantize B, A = 255
- [ ] Contact sheets, channel strip and numbers summary follow the layout
- [ ] Tests from the design's section 6; goldens' summary lines refreshed after the user's look review
- [ ] Reword "the contract Petri reads" (`src/plume/sheet/sheet_json.py`) and similar comments to name no game

## Acceptance / Done When
- A default run writes `channels = "heat,thickness,shade,unused"` with A = 255 and visibly self-shadowed smoke
  on the contact sheets; the normal layout still produces today's sheet.
- The user approves the smoke puff's look in the new default.

## Related
- `docs/specs/2026-11-07-shade-channel-design.md`
- `docs/specs/2026-11-07-plume-design.md` section 10 (A4)
- `docs/backlog/feature-2026-11-07-slice-3-combustion-fireball-plume.md`
- `chadmv/petri`: `docs/specs/2026-11-07-visual-effects-workflow-design.md` sections 6.3 and 6.4 (the guide)

## Resolution
Built in PR #10 (merge 3cf2689): selectable `output.channels` with shade as the default, light volume, thin-pixel easing, A = 255, `render.light_dir`; PC GPU tests green. Chad merged it as the look approval; the golden summary lines were refreshed afterward.
