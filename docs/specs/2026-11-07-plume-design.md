# Plume design

Date: 2026-11-07. Status: approved by the user 2026-11-07, with amendments A1 to A3; section 11 records
changes made while building slice 1. Builds on the confirmed design brief
(`2026-11-07-plume-design-brief.md`, decisions numbered D1 to D34 here); this spec states how, the brief
states what and why. Amendments to the brief are listed in section 10 and need the user's yes.

## 1. What Plume is

A headless command-line tool. An agent writes a TOML recipe, runs `plume run`, and gets a flipbook sheet for
Petri plus the evidence to judge it: contact sheets, a channel strip, a numbers file and the resolved
settings. The same recipe on the same machine and backend gives the same bytes.

## 2. The pipeline

One run is four steps, each producing what the next needs:

1. **Load** (`plume.recipe`): TOML file plus `--preview` and (from slice 2) `extends` and `--set` become one
   frozen, fully resolved `Recipe`. Validation errors stop here with exit code 2.
2. **Simulate and capture** (`plume.sim`, `plume.render`): the solver steps through effect time. At each
   frame time the renderer turns the volume into raw frame images (float heat, thickness and normal over
   the whole domain's view). Only these 2D images are kept, never the volumes.
3. **Assemble** (`plume.sheet`): from all raw frame images, find the crop and seat, resample each frame to
   `frame_px`, soften, normalize heat, quantize, pack the sheet PNG and write the JSON.
4. **Report** (`plume.report`): from the quantized sheet (exactly what Petri sees), write the contact
   sheets, the channel strip, `numbers.txt`, `settings.toml` and `timing.txt`.

## 3. Simulation

### 3.1 Grid and units

- Axes: x right, y up, z toward the default camera. Meters, seconds, Kelvin throughout. The origin is the
  center of the domain's floor.
- Cell counts per axis are `round(size_m / cell_m)`; the actual size (counts times `cell_m`) is logged.
- A MAC (staggered) grid: velocity components on cell faces, scalars (smoke, temperature, and from slice 3
  fuel and flame) at cell centers. Staggering keeps the pressure projection free of checkerboard modes.
- Each of the six faces is `closed` (solid: zero normal velocity) or `open` (pressure 0, material flows
  out). Defaults: bottom closed, the rest open (D24).

### 3.2 One substep, in order

`dt = 1 / (fps * substeps)` where `fps = frames / duration_s` (D25). From slice 2 a CFL cap may add
substeps (D10).

1. **Emit.** Each active emitter blends smoke, temperature and velocity into the cells it covers (3.3).
2. **Forces.** Vertical acceleration `gravity_mps2 * (heat_buoyancy * (T - ambient_k) / ambient_k -
   smoke_weight * smoke)`. With `heat_buoyancy = 1` this is ideal-gas buoyancy (a parcel at density
   proportional to `1 / T` in air at `ambient_k`). From slice 2: wind, drag,
   vorticity confinement, curl-noise turbulence.
3. **Advect velocity**, MacCormack with clamping to the neighborhood's range (D6).
4. **Project.** Compute divergence, solve for pressure, subtract its gradient. Slice 1: red-black
   Gauss-Seidel, `pressure_iterations` sweeps (default 60). Slice 2: geometric multigrid V-cycles behind
   the same function (D7).
5. **Advect scalars**, MacCormack with clamping, using the projected velocity.
6. **Dissipate.** Smoke decays by `exp(-smoke_per_s * dt)`; temperature relaxes toward ambient by
   `exp(-cooling_per_s * dt)`.

`warmup_s` runs these steps before frame 0 (D10). The simulation clock starts at 0 when warmup begins and
emitter times are on that clock. Frame `i` is captured after `warmup_s + (i + 1) / fps` of simulated time,
so the last frame lands at the end of the duration and the first already shows the effect starting.

### 3.3 Emitters

- Shapes: `sphere` (`center_m`, `radius_m`) and `box` (`center_m`, `size_m`).
- Coverage per cell is 1 inside, falling smoothly to 0 across the outer `edge_softness` fraction of the
  shape (smoothstep), times a breakup factor `1 + strength * noise(position / scale_m)`, clamped at 0.
- While `start_s <= t < end_s`: smoke grows by `smoke_per_s * coverage * dt`; temperature moves toward
  `temperature_k` by `coverage`; velocity moves toward `velocity_mps` (or, with `velocity_mode =
  "outward"`, that speed away from the center) by `coverage`.
- Noise is a value-noise lattice whose lattice values come from a counter-based integer hash of
  `(seed, emitter index, lattice cell)`. No other source of randomness exists.

### 3.4 Determinism rules

- Every kernel writes only cells it owns (gather). The emitter blend is a gather too: each cell loops over
  the emitters. Warp's deterministic mode is set to `RUN_TO_RUN` before any module loads, as a guard for
  any scatter added later.
- Fixed iteration counts everywhere; no convergence-dependent loops.
- Host-side reductions (sums, maxima) are done in numpy float64 on copied arrays, in a fixed order.

## 4. Rendering a frame

### 4.1 Camera and the domain view

- Orthographic. The view direction comes from `elevation_deg` (positive looks down) and `azimuth_deg`
  (positive orbits counterclockwise seen from above). Camera space: x right, y up, z toward the camera.
- The domain view is the camera-plane rectangle covering the projection of the domain's eight corners,
  sampled at `px_per_cell` (default 2) pixels per cell. This is the supersampling of D15: the volume holds
  no detail finer than half a cell.

### 4.2 The ray march

One ray per domain-view pixel, front to back, fixed steps of half a cell, trilinear samples. At each step
with smoke `s` and temperature `T`:

- `alpha = 1 - exp(-opacity_per_density * s * step_m)`; transmittance `tr` starts at 1 and is multiplied by
  `1 - alpha`.
- Heat: `heat += glow(T) * step_m * tr ^ smoke_hides_heat`, where `glow(T) = max(0, T - glow_start_k)`
  (slice 3 adds the flame field to this, weighted by `[combustion]` values).
- Normal: `n_sum += tr * alpha * normalize(-grad)`, where `grad` is the gradient of the smoke field after a Gaussian
  blur of `normal_blur_cells` (computed once per frame, central differences, trilinear sampled).

Per pixel the raw outputs are `heat` (physical units, K m), `thickness = 1 - tr` (D12), and the normal:
`n_sum` rotated into camera space and normalized, then blended toward (0, 0, 1) as thickness falls below
`normal_fade_thickness` (default 0.1), then given `z = |z|`.

## 5. Assembling the sheet

1. **Heat scale for the crop.** `h_raw_max` = the largest raw heat over all frames (0 if none).
2. **Content.** A domain-view pixel is content if `thickness >= 0.5 / 255` or `heat >= 0.5 / 255 *
   h_raw_max`, in any frame.
3. **Square crop.** The union box of content, grown on its short side to a square around its center, then
   grown by `crop_margin` of its side on each side. `frame_m` is the square's side in meters.
4. **Resample** each frame's crop to `frame_px` square: bicubic (Pillow, float mode, sub-pixel box), with
   thickness clamped to 0..1 afterward.
5. **Soften** all channels with a separable Gaussian, sigma `soften_px` (numpy). Then renormalize each normal
   to unit length (z from the softened z, kept positive).
6. **Normalize heat** by the largest softened heat in the sequence (`heat_divisor`, logged).
7. **Quantize.** `R = floor(heat * 255 + 0.5)`, `G = floor(thickness * 255 + 0.5)`, `B = floor((nx + 1) *
   127.5 + 0.5)`, `A = floor((ny + 1) * 127.5 + 0.5)`, clamped to 0..255. A pixel with `G = 0` and `R = 0`
   gets `B = A = 128`. So a camera-facing normal reads (128, 128); `A = 255` faces up.
8. **Gutter check.** If any frame has a nonzero R or G byte within 2 px of its edge, grow `crop_margin` by
   2 percent and repeat from step 3 (at most 8 times, then fail loudly).
9. **Seat.** The seat point (D17) projected into the domain view, as fractions of the crop square from the
   top-left, x right, y down. Not clamped.
10. **Pack.** Frames fill rows left to right, top to bottom. `columns` defaults to `ceil(sqrt(frames))`
    (8 for 64 frames); rows is `ceil(frames / columns)`; unused slots are all zero. PNG via Pillow, RGBA,
    `compress_level = 6`, no metadata chunks.
11. **JSON** `<name>.json`: keys exactly `frames, columns, frame_px, fps, frame_m, seat, channels, source,
    tool, written_by`; `seat` is `[x, y]`; floats rounded to 6 decimals; 2-space indent; trailing newline.
    `source` is the recipe path relative to the root of the git repository containing it (forward slashes),
    or the path as given when it is in none. `tool` is `"plume <version>"`. `written_by` is the command as
    typed, `plume` plus its arguments, joined by spaces.

## 6. Reports

### 6.1 Contact sheets

From the quantized sheet. Per pixel, decode `heat = R / 255`, `G = G / 255`, `n = (B, A)` mapped back to -1..1
with `z = sqrt(max(0, 1 - x^2 - y^2))`. Then, in linear color:

`color = background * (1 - G) + G * smoke_ramp(heat) * light(n) + emission_ramp(heat)`

- `light(n) = ambient + (1 - ambient) * max(0, dot(n, sun_dir))`, from `[look]` (defaults: `ambient = 0.55`,
  `sun_dir` up and to the left, toward the camera).
- Ramps are lists of `[position, "#rrggbb"]` stops in sRGB, interpolated in linear. Defaults: smoke runs
  from the reference's gray-brown when cool to warm orange when hot; emission runs from black through red
  and orange to pale yellow.
- Backgrounds: `contact_neutral.png` on sRGB (128, 128, 128), `contact_grass.png` on sRGB (170, 196, 118).
- Each frame shrinks to `contact_px` (default 128) in the sheet's grid, frame index in the top-left corner
  in Pillow's built-in font. Converted to sRGB for viewing.

### 6.2 Channel strip

`channels.png`: six frames evenly spaced from first to last, one row each, four columns at `frame_px`:
heat as gray, thickness as gray, the normal as color (`(n + 1) / 2` as RGB), and the neutral composite.

### 6.3 Numbers

`numbers.txt`, summary first, then one row per frame. Fixed-width, space-separated, 4 decimals for
fractions, 6 for physical values:

```
recipe            recipes/smoke_puff.toml
backend           cuda:0
grid              100 x 150 x 100 cells of 0.020000 m
frames            64
fps               20.000000
frame_m           1.234567
heat_divisor      0.000000 K m
peak_frame        12
fade_frame        51

frame  time_s  coverage  left    top     right   bottom  mean_heat  mean_thick  total_thick  peak_heat
    0  0.0000  0.0123    0.4100  0.6200  0.5900  0.8000  0.0000     0.4210      1234.5678    0.0000
```

- `coverage`: share of the frame's pixels with `G >= 8`. `left .. bottom`: the box of those pixels as frame
  fractions (all `-` when none). `mean_heat` and `mean_thick`: averages over covered pixels, 0 to 1.
  `total_thick`: sum of `G / 255` over the frame. `peak_heat`: largest `R / 255`.
- `peak_frame`: the frame with the largest `total_thick`. `fade_frame`: the first later frame whose
  `total_thick` is under 10 percent of the peak, or `never`.

### 6.4 Settings and timing

- `settings.toml`: the resolved recipe (every value, defaults included, preview overrides applied), plus a
  `[resolved]` table of derived values (cell counts, actual domain size, fps, dt, substeps, device, Warp
  version). Valid as a recipe: `plume run settings.toml` reproduces the run.
- `timing.txt`: wall-clock seconds per stage. The only output not covered by the same-bytes promise.

## 7. Command line

- `plume run RECIPE [--preview] [--device auto|cuda|cpu] [--out DIR]` (slice 2 adds `--set KEY=VALUE`).
  Writes to `DIR` or `out/<output.name>/`, and `preview/` inside it for `--preview`. Prints a summary:
  every output path, the grid, backend, run time, `peak_frame`, `fade_frame`, `frame_m`.
- `plume check RECIPE [--preview]`: validates and prints the resolved settings and grid; no simulation.
- `plume version`.
- Exit codes: 0 success, 2 recipe error (message names the key and, for unknown keys, the closest valid
  one), 1 anything else.
- `--preview` (D30): cells coarsened so the longest axis has `preview.longest_axis_cells` (48), `frames =
  preview.frames` (16), `frame_px = preview.frame_px` (128), same duration.

## 8. The recipe, slice 1 keys

Names carry units (D20); unknown keys are errors. Defaults in brackets.

- top level: `seed` [0]
- `[domain]`: `size_m` (required), `cell_m` (required), `ambient_k` [293], `faces` table with `bottom`
  ["closed"], `top`, `left`, `right`, `front`, `back` ["open"]
- `[time]`: `duration_s` (required), `frames` [64], `substeps` [3], `warmup_s` [0]
- `[[emitter]]`: `name` (required), `shape` ["sphere"], `center_m` (required), `radius_m` (sphere),
  `size_m` (box), `edge_softness` [0.3], `start_s` [0], `end_s` (required), `smoke_per_s` [0],
  `temperature_k` [-1, meaning ambient], `velocity_mps` [0, 0, 0], `velocity_mode` ["fixed"], `noise` table:
  `scale_m` [0.1], `strength` [0]
- `[forces]`: `gravity_mps2` [9.81], `heat_buoyancy` [1], `smoke_weight` [0]
- `[dissipation]`: `smoke_per_s` [0], `cooling_per_s` [0]
- `[solver]`: `pressure_iterations` [60]
- `[camera]`: `elevation_deg` [0], `azimuth_deg` [0], `seat` [first emitter's name] (a point in meters
  arrives when an effect needs one)
- `[render]`: `px_per_cell` [2], `opacity_per_density` [4], `glow_start_k` [600], `smoke_hides_heat` [1],
  `normal_blur_cells` [1.5], `normal_fade_thickness` [0.1], `soften_px` [0.75], `crop_margin` [0.04]
- `[output]`: `name` [recipe file stem; a plain file name, no paths], `frame_px` [256], `columns` [0, meaning
  the smallest square grid]
- `[preview]`: `longest_axis_cells` [48], `frames` [16], `frame_px` [128]
- `[look]`: `ambient`, `sun_dir`, `smoke_ramp`, `emission_ramp`, `contact_px` [128], `backgrounds`

The schema is one table in code (name, type, unit, default, description), and `docs/recipe-reference.md`
is generated from it (D33).

## 9. Success criteria

- **Slice 1:** `plume run recipes/smoke_puff.toml` writes all eight outputs. A soft puff rises and thins, it
  fills its frames, and normals shade it as a rounded form on the contact sheet. `--preview` takes under 10
  s on the 2080 Ti and under 30 s on CPU (Windows and WSL Ubuntu). Two identical runs give identical bytes
  in all outputs but `timing.txt`. CI is green on Linux CPU.
- **Whole first version:** a default run (about 128 cubed, 64 frames, 256 px) finishes in under 60 s on
  the 2080 Ti; the fireball plume, impact dust, building fire and chimney smoke recipes each pass the user's
  look review against the reference.

## 10. Amendments to the brief (need the user's yes)

- **A1 - Keep 2D frame images, not volumes (changes D16's internals).** The brief said the run keeps each
  frame's volume, then renders at the final crop. At close-up size (256 x 384 x 256 cells, 64 frames, two
  fields) that is about 6 GB even at half precision. Instead each frame is rendered once over the whole
  domain view at 2 px per cell and only those images are kept (about 85 MB at the default size, 500 MB at
  close-up size, as 32-bit floats), then cropped and resampled.
  No detail is lost: the volume has none finer than half a cell. The crop rule, gutter and margin are
  unchanged.
- **A2 - Run time moves out of `numbers.txt` (changes D19).** A wall-clock time inside `numbers.txt` would
  break the same-bytes promise. Run time goes to stdout and to a new `timing.txt`, the one output excluded
  from that promise.
- **A3 - A `[solver]` section (extends D21).** Solver controls (`pressure_iterations` now; multigrid cycle
  counts in slice 2) get their own section rather than hiding in `[time]` or `[domain]`.

## 11. Changes while building slice 1

- Frame times are `(i + 1) / fps` after warmup (3.2), not `i / fps`, so frame 0 is never empty.
- Normals average unit surface directions (4.2), so sharp and soft edges weigh alike.
- `seat` names an emitter only (8); `output.name` must be a plain file name (a security review found that
  `../` in it could write outside the output folder).
- Advection loses some smoke: a small, sharp puff loses about 10 percent over 40 steps (plain
  semi-Lagrangian about 7). The projection leaves almost no divergence, so this is the scheme, not a leak.
- Measured on the 2080 Ti: the smoke puff preview takes about 5 s warm and the full sheet (80 x 100 x 80
  cells, 64 frames at 256 px) about 15 s; the CPU preview takes about 13 s on Windows. The first run on a
  device adds about 20 s of kernel compiling.

## 12. Risks

- **Warp on CPU is slow.** Measured on this PC (Warp 1.19.0): a simple 128-cubed pass takes 12.8 ms on CPU
  against 0.06 ms on the 2080 Ti. The CPU path is for previews (48 cells on the long axis, about 14 times
  fewer cells than 128 cubed); full CPU runs will be slow, and that is accepted.
- **The 2080 Ti is Warp's minimum GPU** (sm_75). Mitigated by the exact pin (D2).
- **Look tuning is open-ended.** Every slice ends with the user's look review of its example recipe; numbers
  catch regressions, eyes judge the look.
