# Shade channel and selectable channel layouts (design)

Date: 2026-11-07. Status: direction chosen by the user 2026-11-07 ("selectable layout, shade default");
this document is the detail for review. Amends the design brief's sheet contract section and D14 and D18,
and the design spec (sections 4.2, 5, 6.1, 6.2, 8). Tracked by
`docs/backlog/feature-2026-11-07-shade-channel-layout.md`.

## Plain version

A sheet's blue and alpha channels can now hold one of two things, picked in the recipe:

- **shade** (the new default): how lit the smoke is by a key light, with the smoke's own shadow baked in, in
  blue; alpha is unused and always 255. A game multiplies its smoke color by it and gets a dense, rounded,
  self-shadowed body without any lighting math of its own.
- **normal** (what Plume writes today): the smoke surface's camera-space normal x and y, so a game can light
  the card itself.

The JSON's `channels` string says which one a sheet holds, so a game can check it.

## 1. Why

A normal lights a flipbook card as one smooth surface: the side away from the light darkens evenly and the
card's edge gets a rim, but the smoke never shadows itself. Real explosion flipbooks read dense because the
far side of each billow sits in the shadow of the near side. A baked shade carries that, costs the game one
multiply, and frees the alpha channel.

The guide for this is Petri (`chadmv/petri`), which changed its own sheet format to shade after a look
review of its fireball (its spec `docs/specs/2026-11-07-visual-effects-workflow-design.md`, section 6.3). Plume
does not depend on Petri: both layouts are general, and nothing in Plume names a game. Petri simply asks for
the default.

## 2. The recipe

One new key under `[output]` and four under `[render]`, all in `src/plume/recipe/schema.py` (the one table of
keys; the reference is regenerated):

| key | default | meaning |
|---|---|---|
| `output.channels` | `"heat,thickness,shade,unused"` | The sheet's channel layout, R, G, B, A. One of `"heat,thickness,shade,unused"` or `"heat,thickness,normal_x,normal_y"`. Written verbatim to the JSON's `channels`. |
| `render.light_dir` | `(-0.5, 0.7, 0.5)` | Direction toward the key light in camera space (x right, y up, z toward the camera): above, leaning left and toward the camera. Moved from `look.sun_dir`, so the baked shade and the contact sheet's normal lighting share one light. |
| `render.shade_fill` | `0.25` | Share of light every scattering point gets regardless of shadow (sky and bounce), 0 to 1. |
| `render.shade_fade_thickness` | `0.1` | Below this thickness the shade eases into its neighborhood's value (section 4). |
| `render.shade_neighborhood_px` | `4.0` | Sigma, in frame pixels, of the neighborhood a thin pixel takes its shade from. |

The layout string itself is the recipe value, so the JSON and the recipe cannot disagree (one definition).
`check` rejects any other string with the two valid ones in the message. `look.sun_dir` is removed; a recipe
that sets it fails with the closest-name hint pointing at `render.light_dir`.

## 3. The shade pass (render)

Per captured frame, before the camera march:

1. **Light volume.** For every cell, march from its center toward the light (`light_dir` turned into world
   space by the camera) in fixed half-cell steps with trilinear smoke samples until the ray leaves the
   domain, and store `light = exp(-opacity_per_density * column_density_m)`: the share of key light reaching
   that cell. One thread per cell writes only its own cell (a gather), fixed step counts, so it keeps the
   determinism rules. Cost: at 128 cubed, about 2 million cells times at most about 440 half-cell steps; the
   preview grid is about 14 times smaller.
2. **Camera march** (spec 4.2) gains one sum: at each step `shade_sum += tr * alpha * (shade_fill + (1 -
   shade_fill) * light(sample))`. The raw shade is `shade_sum / thickness` where thickness is above zero, and
   0 where it is not: the opacity-weighted light reaching the smoke the camera sees. The normal sums are
   skipped in the shade layout and the shade sum in the normal layout.

The raw frame keeps the same five floats (heat, thickness and three more); in the shade layout the last
three are shade, 0, 0.

## 4. Assembling a shade sheet (spec section 5)

Steps 1 to 4 (crop, resample) are unchanged. Then:

5. **Soften** all channels with `soften_px` as now (shade is not renormalized).
6. **Ease thin pixels.** The neighborhood value is `blur(shade * thickness) / blur(thickness)` with a Gaussian
   of sigma `shade_neighborhood_px` (where the blurred thickness is zero, the frame's thickness-weighted mean
   shade). Each pixel's shade becomes `lerp(neighborhood, shade, w)` with `w = clamp(thickness /
   shade_fade_thickness, 0, 1)`. A thin edge (and every empty pixel) then carries the shade of the body it
   belongs to, so it neither speckles nor draws a dark outline when a game filters or mipmaps the sheet.
7. **Normalize shade** by the largest shade over every pixel with thickness at least `shade_fade_thickness`
   in the whole sequence (`shade_divisor`, logged like `heat_divisor`), so 1 means the brightest well-covered
   smoke of the run on every frame. Heat is normalized as now.
8. **Quantize.** `B = floor(shade * 255 + 0.5)`, `A = 255`. R and G as now.

The gutter check, seat, pack and JSON steps are unchanged except that `channels` is `output.channels`. The
normal layout keeps today's steps exactly.

## 5. Reports

- **Contact sheets** (spec 6.1). The shade layout lights the smoke from the sheet:
  `color = background * (1 - G) + G * smoke_ramp(heat) * (1 - look.shade_depth * (1 - shade)) +
  emission_ramp(heat)`, with a new `look.shade_depth` (default 0.75, 0 ignores the shade, 1 takes the
  shadowed parts to black). The normal layout keeps `light(n)`, now from `render.light_dir`.
- **Channel strip** (spec 6.2). The third column shows shade as gray in the shade layout and the normal as
  color in the normal layout; its title says which.
- **Numbers** (spec 6.3). The summary gains `channels` and, in the shade layout, `shade_divisor`. The
  per-frame table is unchanged, so slice 1 and 2 golden tables stay valid; the summary lines are refreshed
  in the goldens once, with the user's look review of the smoke puff in the new default.

## 6. Tests (CPU, tiny grids)

- Layout: each `output.channels` value lands verbatim in the JSON; any other string is a recipe error (exit
  code 2) naming the valid ones; `look.sun_dir` is rejected with a hint to `render.light_dir`.
- Shade sheet bytes: every A byte is 255; empty pixels carry their eased neighborhood shade, not 0.
- Self-shadowing: a still sphere of smoke lit from the left has a mean shade on its left half clearly above
  its right half; with `shade_fill = 1` the two halves match (no shadow).
- Thin easing: a dense ball with a thin halo shows no halo pixel darker than the ball's shaded side by more
  than a small tolerance.
- Normal layout: today's normal tests still pass unchanged with `output.channels` set to the normal layout.
- Determinism: the existing same-bytes tests run in both layouts; the GPU same-bytes test covers the light
  volume kernel.

## 7. What does not change

Frame geometry, cropping, gutter, seat, packing, JSON keys and their order, heat and thickness, and the
determinism promise. A game reading only R and G sees no difference.

## 8. Rejected

- **Shade only (drop normals).** Simpler, but a game that lights cards itself (or wants six-way lighting
  later) loses the option; the normal path already exists and is tested.
- **Shade in B and normal x and y squeezed elsewhere.** Four 8-bit channels have no room; a second sheet per
  flipbook doubles a game's texture memory for a layout nobody has asked for.
- **Light direction per layout (keeping `look.sun_dir` beside a bake light).** Two lights that should agree
  would drift; one `render.light_dir` serves both.
- **Six-way lighting (six baked light directions in two sheets).** The known upgrade if a single baked light
  reads flat; a separate item when a look review asks for it.
