# Shade channel layout plan

Date: 2026-11-07. Builds `docs/backlog/feature-2026-11-07-shade-channel-layout.md` from the settled design
`docs/specs/2026-11-07-shade-channel-design.md` (amendment A4 of the design spec). The design is settled, so
this goes straight from intake to plan; no design interview.

## Corrections to inputs

- The design's section 2 says `look.sun_dir` fails "with the closest-name hint pointing at
  `render.light_dir`". The loader's hint is a fuzzy match within the same table, so it would point at a
  `look` key. T1 adds a small moved-keys table to the schema (`look.sun_dir` -> `render.light_dir`) that the
  unknown-key message checks first.
- The design's section 4 leaves two empty cases open; this plan settles them:
  - a frame with no thickness anywhere has no neighborhood mean, so its shade is 0 (G is 0 there, so a game
    never sees it);
  - a run with no pixel at least `shade_fade_thickness` thick has no well-covered smoke to normalize by, so
    `shade_divisor` falls back to the largest shade of any pixel with thickness, and to 1 when there is
    none.
- Found while building T3: the design keeps the plain shade in the raw frame and resamples and softens it
  like any channel. Those filters then mix an edge pixel's shade with the 0 of the empty pixels beside it,
  which drew the dark outline the easing step exists to prevent (a test ball's darkest edge byte fell from
  85 to 7). The raw frame keeps shade times thickness instead, so every filter weighs a pixel's shade by
  its smoke, as it already does the thickness, and the easing step divides it back out. The easing's
  "where the blurred thickness is zero" becomes a smooth lean toward the frame's mean (the mean counts as
  1/255 of thickness in every neighborhood): bicubic ringing leaves faint pixels with thickness and no
  shade, and a hard zero test let their neighborhoods read 0.
- Padding (resample) and empty space (ray march) are layout-specific: the normal layout's empty pixel faces
  the camera (normal z = 1); the shade layout's is all zero. `render/raw_frame.py` gets one definition of
  the empty pixel per layout.

## Tasks

Every task touches `recipe/schema.py` or reads the layout it defines, so they run in sequence.

### T1 - Recipe keys (pipeline)

- `schema.py`: `SHADE_LAYOUT = "heat,thickness,shade,unused"`, `NORMAL_LAYOUT = "heat,thickness,normal_x,normal_y"`,
  `CHANNEL_LAYOUTS`; `output.channels` (choices `CHANNEL_LAYOUTS`, default shade); `render.light_dir`,
  `render.shade_fill`, `render.shade_fade_thickness`, `render.shade_neighborhood_px`; `look.shade_depth`;
  `look.sun_dir` removed; `MOVED_KEYS`.
- `rules.py`: `light_dir` has length; `shade_fill` and `shade_depth` 0 to 1; the other two above 0.
- `build.py`: unknown-key message names the new place of a moved key.
- Reference regenerated.
- Tests: each layout parses; another string is a recipe error naming both; `look.sun_dir` names
  `render.light_dir`; a zero `light_dir` fails.

### T2 - Light volume and shade sum (kernel)

- `render/light_volume.py`: one thread per cell marches from its center toward the light in half-cell
  steps (step count fixed by the ray's length inside the domain) with trilinear smoke samples and writes
  `exp(-opacity_per_density * column_density_m)`.
- `raymarch.py`: a layout flag; in the shade layout the march adds `tr * alpha * (fill + (1 - fill) *
  light)` and writes shade, 0, 0; the normal sums run in the normal layout only. `FrameRenderer` skips the
  normal field in the shade layout and the light volume in the normal layout.
- Tests (CPU, 16 cubed): a sphere lit from the left has a brighter left half; `shade_fill = 1` makes the
  halves match; a uniform slab lit from straight in front has light falling with depth as Beer-Lambert;
  today's normal tests pass with the normal layout.

### T3 - Sheet assembly (pipeline)

- `soften.py` renormalizes normals in the normal layout only; `resample.py` pads with the layout's empty
  pixel.
- `sheet/shade.py`: thin-pixel easing and `shade_divisor` (design section 4, steps 6 and 7).
- `quantize.py`: shade layout B = shade / divisor, A = 255; the normal layout is unchanged.
- `assemble.py`: the steps in order; `AssembledFrames.shade_divisor`.
- `sheet_json.py`: `channels` from the recipe; the docstring names no game.
- Tests: every A byte is 255; empty pixels carry eased shade, not 0; a dense ball with a thin halo has no
  halo pixel darker than the ball's shaded side by more than a small tolerance; JSON carries each layout.

### T4 - Reports and CLI (pipeline)

- `composite.py`: decode and light by layout (design section 5) with `render.light_dir`; `look.shade_depth`.
- `channels.py`: third column titled and drawn by layout.
- `numbers.py`: summary gains `channels` and, in the shade layout, `shade_divisor`.
- `cli/run.py`: passes the layout and light through.
- Tests: the composite darkens with shade and ignores it at `shade_depth = 0`; the same-bytes test runs in
  both layouts; the run writes each layout's `channels`.

### T5 - Wording and docs

- Comments that name a game (`sheet_json.py`, `numbers.py`, `composite.py`, `schema.py`'s grass
  background) say "a game" instead.
- `docs/look-tuning.md`: the shade keys.

### T6 - Look review (look-tuner, then the user)

- Run the smoke puff preview and full sheet in the new default, show the user the contact sheets and the
  channel strip. On approval, refresh the golden's summary lines from a fresh preview of the committed
  recipe. The golden test compares the per-frame table, which the shade does not change.

## Checks before the pull request

- `uv run pytest` on CPU (the `gpu` tests skip in the cloud). The GPU same-bytes test covers the light
  volume kernel and waits for a PC run.
- Timing: the light volume's cost on the preview, CPU, against the 30 s preview budget.
