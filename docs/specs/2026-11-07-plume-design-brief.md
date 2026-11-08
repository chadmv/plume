# Plume design brief

Date: 2026-11-07. Status: confirmed by the user 2026-11-07, including the 60 s final-run budget. Source:
the design interview, rounds 1 to 3 (Q1 to Q34), every answer "recommended". The spec
(`2026-11-07-plume-design.md`) builds on this brief and lists its amendments.

## Intent

Plume is a fire, smoke and explosion simulator that renders flipbook sheets for realtime games. It is built
for an LLM agent to drive, not for a human at a GUI: the agent writes a text recipe, runs it, looks at the
contact sheets and numbers, and iterates in seconds.

The first consumer is Petri, a cozy town builder in Godot 4.7, which needs a fireball's flame plume turning
to smoke, dust clouds, smoke puffs and building fires. Plume replaces the plan of scripting Blender's
Mantaflow, which takes minutes per rerun and is built for a human tuning a viewport.

The look is soft, warm, storybook fire, never photographic. The reference is Petri's
`docs/art-direction/reference/fireball-impact-meadow.png`: a glowing rock bursting into earth, flame
streaming up and turning into soft gray-brown smoke, with a low dust skirt along the ground. Petri colors heat
through a ramp in the game, so the sheet stays grayscale data.

## The sheet contract (fixed by the user's request)

Amended 2026-11-07 by `2026-11-07-shade-channel-design.md`: B and A are chosen per recipe, either shade and
unused (the default) or normal x and y as below; the JSON's `channels` names the layout.

- One RGBA PNG per flipbook, frames in rows, left to right and top to bottom.
  - R = heat (emission), normalized to the hottest frame of the whole sequence.
  - G = thickness (smoke density as alpha).
  - B, A = camera-space normal x and y of the smoke surface, -1..1 mapped to 0..255; z is rebuilt.
  - All 8-bit linear, lightly softened (painterly, never grainy).
- Default 64 frames of 256 px on a 2048 px sheet (8 x 8); 512 px frames on 4096 for close-ups.
- Every frame cropped to the union of all frames' bounds.
- A JSON beside it with, in this order: `frames`, `columns`, `frame_px`, `fps` (frames per second of effect
  time), `frame_m` (frame width in meters), `seat` (the emitter's point in the frame, as fractions),
  `channels` (`"heat,thickness,normal_x,normal_y"`), `source` (the recipe path), `tool`, `written_by`.
- Per run, also: two contact sheets (neutral and grass backgrounds), a numbers file, a resolved settings log.
- `--preview` mode; headless; seeded and reproducible; GPU on the user's RTX 2080 Ti, CPU on Linux without a
  GPU.

## Settled decisions

### Foundations (round 1)

1. **Stack.** Python 3.13 with NVIDIA Warp, plus numpy and Pillow, environments by uv. One kernel source runs
   on CUDA and on CPU; kernels compile in seconds; Warp ships monthly and has a deterministic mode.
2. **Pinning.** An exact Warp version is pinned in `uv.lock` and upgraded only on purpose, with a test run.
   The 2080 Ti (Turing, sm_75) is exactly Warp's minimum GPU, so a future release could drop it.
3. **Determinism.** Kernels are gather stencils (each thread writes only its own cell). Warp's `RUN_TO_RUN`
   deterministic mode covers the few scatters (emitter splats). All randomness comes from the recipe's `seed`
   through a counter-based hash. Same machine and backend: byte-identical files. CPU against GPU: within a
   tolerance.
4. **CPU path.** The same kernels on `device="cpu"`, chosen by `--device auto|cuda|cpu`; `auto` falls back to
   CPU. `--preview` on CPU is the cloud workflow, verified in WSL Ubuntu and in CI.
5. **Grid.** One dense, fixed box in meters with the cell size from the recipe; about 128 cubed by default,
   up to about 256 x 384 x 256 for 512 px close-ups. The box can be taller than wide.
6. **Advection.** MacCormack with clamping (Selle 2008). Softness comes from named dissipation values and the
   soften pass, not from numerical blur.
7. **Pressure.** Geometric multigrid with a fixed number of V-cycles per step. Slice 1 may ship a fixed-count
   red-black Gauss-Seidel solver behind the same interface.
8. **Combustion.** A fuel model: fields fuel, temperature, smoke, velocity, and flame (burning right now).
   Above the ignition temperature fuel burns at a set rate, releasing heat, smoke and expansion; heat rises
   and cools. R is a recipe-weighted blend of flame and the hot part of temperature. Slice 1 uses smoke,
   temperature and velocity only.
9. **Forces.** Heat buoyancy and smoke weight (separate values), gravity, constant wind, vorticity
   confinement (Fedkiw 2001), seeded curl-noise turbulence (scale, strength, speed), drag. Each is off or
   neutral unless set.
10. **Time stepping.** `substeps` per frame (about 2 to 4) plus a CFL safety cap computed with deterministic
    arithmetic; the resolved count goes in the log. `warmup_s` runs the sim before frame 0.

### Renderer and sheet (round 2)

11. **Camera.** Orthographic, so `frame_m` is one true number. `elevation_deg` (default 0, a level side view
    that reads on an upright billboard from any yaw) and `azimuth_deg` (default 0).
12. **Thickness (G).** Beer-Lambert opacity, `1 - exp(-opacity_per_density * column density)`. Absolute, not
    normalized, so sheets compare. Smoke only; flame shows through R.
13. **Heat (R).** Gathered front to back and hidden by smoke in front, with `smoke_hides_heat` from 0 to 1
    (default 1). Normalized by the exact maximum over the whole sequence, measured after softening. The
    divisor is logged in physical units. Linear.
14. **Normals (B, A).** The opacity-weighted average, along each ray, of the gradient of a pre-blurred density
    (`normal_blur_cells`, default 1.5), turned into camera space and renormalized. Where G is near 0 the
    normal fades to face the camera. Encoding `round((n + 1) * 127.5)`, so facing the camera reads (128,
    128); +x right, +y up on screen (OpenGL and Godot style); z rebuilt as `sqrt(1 - x^2 - y^2)`.
15. **Softening.** No randomness in the renderer: fixed half-cell steps with trilinear sampling, rendered at
    twice the frame size and averaged down, then a light 2D Gaussian `soften_px` (default 0.75 px) on all
    channels, with normals renormalized afterward.
16. **Crop.** Content is any pixel whose R or G byte would be at least 1. The union over all frames is grown
    to a square centered on the content, plus `crop_margin` (default 4 percent per side), always leaving at
    least a 2 px empty gutter so mipmaps never bleed between frames. The run keeps each frame's volume, finds
    the crop, then renders at final resolution. `frame_m` is the square's side.
17. **Seat.** By default the first emitter's center; a recipe may name another emitter or give a point in
    meters. Fractions from the top-left, x right and y down (Godot's UV origin). It may fall outside 0..1.
18. **Contact sheets.** The reference composite, which Petri's shader is to match:
    `color = background * (1 - G) + G * smoke_color(heat) * light(normal) + emission_ramp(R)` (premultiplied).
    Ramps live in the recipe's `[look]`. Backgrounds: neutral sRGB (128, 128, 128) and Petri's mid grass,
    sRGB (170, 196, 118). Files `contact_neutral.png` and `contact_grass.png`, 128 px thumbnails in the sheet's
    grid with frame numbers. Plus `channels.png`: six evenly spaced frames at full size, each channel shown
    separately.
19. **Numbers file.** One `numbers.txt`: a summary block (peak thickness frame, first frame after it under 10
    percent of peak or "never", heat divisor, `frame_m`, run time, backend), then a fixed-width table, one row
    per frame: `frame`, `time_s`, `coverage` (share of pixels with G of at least 8/255), `bbox` (frame
    fractions), `mean_heat` (over covered pixels), `mean_thickness`, `total_thickness`, `peak_heat`.

### Recipe, CLI, repo and process (round 3)

20. **Recipe format.** TOML read by `tomllib`. Every name carries its unit (`radius_m`, `start_s`,
    `elevation_deg`, `wind_mps`, `temperature_k`). Temperature is absolute Kelvin with `ambient_k = 293` and
    Boussinesq buoyancy. Unknown keys are errors with a "did you mean" hint. Every default is logged.
21. **Recipe shape.** Top-level `seed`; sections `[domain]`, `[time]`, `[[emitter]]`, `[forces]`,
    `[dissipation]`, `[combustion]`, `[camera]`, `[render]`, `[output]`, `[preview]`, `[look]`. `[look]` never
    affects the sheet.
22. **Emitters.** Sphere and box shapes. Each adds any of smoke, temperature, fuel and velocity, with a soft
    edge and seeded noise breakup. Any numeric emitter value can be keyframed as `[[time_s, value], ...]`,
    linearly interpolated. `velocity_mode = "outward"` for bursts.
23. **Variations.** `extends = "<parent>.toml"` (one parent, deep-merged) and `--set key=value` on the command
    line. Both resolve into the settings log.
24. **Boundaries.** Each face is `closed` or `open`; the floor is closed by default (dust rolls along the
    ground), sides and top open.
25. **Time.** `duration_s` and `frames` in the recipe; `fps = frames / duration_s` in the JSON. Frames are
    evenly spaced samples of effect time.
26. **Looping.** In the first version, as its own slice: run to a steady state, capture a span, crossfade its
    last frames into its first (`loop = true`, `loop_blend_frames = 8`).
27. **CLI.** `plume run recipe.toml [--preview] [--device auto|cuda|cpu] [--out DIR] [--set key=value ...]`,
    `plume check recipe.toml` (validate and print the resolved settings and grid size without simulating),
    `plume version`. `run` prints a short summary: output paths, grid, backend, run time, peak frame, fade
    frame, crop size. Exit codes 0 success, 2 recipe error, 1 anything else.
28. **Outputs.** `out/<name>/` by default (gitignored), or `--out` anywhere; Plume never writes into Petri on
    its own. Files: `<name>.png`, `<name>.json`, `contact_neutral.png`, `contact_grass.png`, `channels.png`,
    `numbers.txt`, `settings.toml` (the resolved recipe, itself rerunnable). Previews go to
    `out/<name>/preview/`. `source` is the recipe path relative to its git repository, forward slashes.
    `tool` is `"plume <version>"`. `written_by` is the exact command that produced the sheet. JSON keys in the
    contract's order, 2-space indent, trailing newline, floats rounded to 6 decimals.
29. **Game recipes** live in Petri beside the effects that use them. Plume keeps examples and test recipes
    in `recipes/`.
30. **Preview.** Same domain in meters, cells coarsened so the longest axis is 48; 16 frames over the same
    duration at 128 px. Turbulence and noise are in meters and vorticity scales with cell size, so a preview
    is a coarse version of the final look. Targets: under 10 s on the 2080 Ti, under 30 s on CPU. Every
    value overridable in `[preview]`.
31. **Repo layout.** By feature, tests mirroring it: `src/plume/{cli,recipe,sim,render,sheet,report}/`,
    `recipes/`, `tests/`, `docs/{specs,plans,retros,backlog}/`, `CLAUDE.md`, `README.md`, `pyproject.toml`,
    `uv.lock`, `.python-version` (3.13). Dependencies: warp-lang (pinned), numpy, Pillow, tomli-w; pytest for
    development.
32. **Tests and CI.** Solver checks on CPU at tiny grids (divergence after projection, constant field
    preserved by advection, hot smoke rises, smoke conserved within a stated percentage); format checks
    (sheet size and grid, channel encoding, JSON keys and order); determinism (two runs, identical bytes);
    golden `numbers.txt` per example recipe within a tolerance; CPU against GPU within a tolerance, skipped
    without a GPU. GitHub Actions on Linux CPU runs all but the GPU test.
33. **Docs.** `CLAUDE.md` (running, conventions, the iterate loop); `README.md` (for people, including the
    Godot import settings a sheet needs: Lossless, mipmaps on, Detect 3D off); `docs/recipe-reference.md`
    generated from the schema, with a test that fails when it is stale; `docs/look-tuning.md`, a "what I see
    to which value" cheat sheet.
34. **Slice order.**
    1. Buoyant smoke puff end to end: every output, CPU and GPU, `--preview`, determinism test, Gauss-Seidel
       pressure.
    2. Solver quality and iteration tools: multigrid, vorticity, curl noise, wind, CFL cap, `extends`,
       `--set`.
    3. Combustion: a fireball plume recipe judged against the reference.
    4. Keyframed and burst emitters, with ground dust.
    5. Looping sheets: a building fire and chimney smoke.
    6. 512 px close-ups and a performance pass.

## Rejected alternatives

- **Taichi.** Upstream's last release is v1.7.4 (July 31) with no Python 3.13 wheels; the only recent
  activity is a community fork whose own pages disagree about its package name and current line.
- **C++ with CUDA.** Fastest, but needs a second, CPU code path.
- **C++ with Vulkan compute (lavapipe on CPU).** One code path, far more engineering.
- **A sparse or adaptive grid, or Warp's NanoVDB volumes.** Unneeded at these sizes; NanoVDB volumes are
  mostly read-only.
- **Plain semi-Lagrangian advection.** Blur grows with coarser grids, so preview and final would differ.
- **PCG pressure.** A global reduction every iteration: slower, with more determinism pitfalls.
- **Level-set fire (Nguyen 2002).** Photoreal-oriented; more than a storybook look needs.
- **A perspective camera.** `frame_m` would not be one number.
- **G normalized to its peak.** Thin smoke would stop reading as thin; sheets would not compare.
- **Percentile heat normalization.** Departs from the contract; softening already removes spikes.
- **Normals from the 2D gradient of G.** Puffier but blind to depth.
- **Jittered or random ray sampling.** Grain.
- **Golden image hashes.** Churn on every look change.
- **Absolute `source` paths.** Differ between machines.
- **`written_by` as a person or agent name.** The command reproduces the sheet; a name does not.
- **Game recipes kept in Plume.** They change with Petri's effects, so they live there.

## Constraints confirmed

- Determinism: same recipe, same machine and backend gives the same bytes; one seed drives all randomness.
- Headless and command-line only; no window. (Amended 2026-11-08 by A5 in `2026-11-08-live-viewer-design.md`:
  `run` and `check` stay headless; `view` is an optional window for judging and tuning.)
- The sheet contract above is the user's and is matched exactly.
- Petri imports sheets Lossless with Detect 3D off; Godot's default 3D detection switches to VRAM
  Compressed, which Godot rates "Moderate" quality loss.
- House style: American spelling, no em or en dashes, descriptive names, plain language first.
- Code organization: one responsibility per file, folders by feature, tests mirror the source.

## Deliberately deferred

- Motion vectors and six-way lighting maps.
- Obstacles inside the domain (the rock, a wall).
- A sparse or adaptive grid.
- Sparks and embers (Petri particles, not sheets).
- Disc and line emitter shapes, until an effect needs them.

## Left for the spec (proposed, needs the user's yes with this brief)

- **Final-run time budget.** Proposed: a default run (about 128 cubed, 64 frames, 256 px) finishes in under
  60 s on the 2080 Ti. Measured in slice 1; slice 6 tightens it.

## Sources

- Warp on PyPI (1.19.0, Nov 2, 2026; Python 3.10+; CPU and CUDA wheels; R580+ driver; Turing minimum):
  https://pypi.org/project/warp-lang/
- Warp deterministic execution: https://nvidia.github.io/warp/stable/user_guide/execution_and_performance/deterministic_execution.html
- Taichi releases: https://github.com/taichi-dev/taichi/releases
- Taichi on PyPI: https://pypi.org/project/taichi/ ; Taichi Forge: https://pypi.org/project/taichi-forge/
- Python `tomllib`: https://docs.python.org/3/library/tomllib.html ; tomli-w 1.2.0: https://pypi.org/project/tomli-w/
- Godot normal map convention: https://docs.godotengine.org/en/stable/tutorials/3d/standard_material_3d.html
- Godot image import (Detect 3D, Lossless): https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_images.html
- GitHub Actions billing (free standard runners for public repos): https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Petri grass colors: `godot/project/world/meadow/meadow_style.gd` lines 111 to 112 in the `chadmv/petri`
  repository.
- Papers: Stam, "Stable Fluids" (SIGGRAPH 1999); Fedkiw, Stam and Jensen, "Visual Simulation of Smoke"
  (SIGGRAPH 2001); Selle et al., "An Unconditionally Stable MacCormack Method" (J. Sci. Comput. 2008);
  Nguyen, Fedkiw and Jensen, "Physically Based Modeling and Animation of Fire" (SIGGRAPH 2002).
