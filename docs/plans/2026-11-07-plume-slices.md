# Plume build plan

Date: 2026-11-07. Status: draft for the user's review. Builds the spec
(`docs/specs/2026-11-07-plume-design.md`) in six slices (D34). Slice 1 is planned task by task; later slices
are outlined and get their own task plans when they start.

## How work proceeds

- Each task: write the tests first where the behavior is checkable, make them pass, commit. One commit per
  task on this session's branch; a pull request to `main` at the end of each slice.
- Every solver and render test runs on CPU at tiny grids, so the whole suite runs in CI and in cloud
  sessions. GPU-only tests are marked `gpu` and skip without a GPU.
- Each slice ends with the user's look review of its example recipe: I send the contact sheets and channel
  strip, the user rules, and the numbers of the approved run become the golden file.
- A retro in `docs/retros/` closes each slice.

## Slice 1 - Buoyant smoke puff, end to end

Done when the spec's slice 1 success criteria (section 9) hold.

### T1.1 - Project scaffold

- `pyproject.toml` (uv, `src/` layout, script `plume = "plume.cli.main:main"`, Python `>=3.13,<3.14`),
  `.python-version` (3.13), `uv.lock`. Dependencies: `warp-lang==1.19.0`, numpy, Pillow, tomli-w; dev:
  pytest. `.gitignore` (`out/`, `.venv/`, caches).
- `src/plume/__init__.py` holds `__version__ = "0.1.0"`; `plume version` prints `plume 0.1.0`.
- `pytest.ini` options: the `gpu` marker; `tests/conftest.py` provides a `device` fixture (CPU) and a
  `cuda_device` fixture that skips without a GPU.
- Test: `plume version` output. Done when `uv run pytest` passes.

### T1.2 - Recipe schema, loading and `plume check`

- `recipe/schema.py`: the one table of keys (section, name, type, unit, default, description) from spec
  section 8.
- `recipe/model.py`: frozen dataclasses for the resolved recipe.
- `recipe/load.py`: TOML to model. Unknown keys fail with the closest valid name (difflib); wrong types and
  missing required values fail naming the key; defaults filled from the schema.
- `recipe/preview.py`: applies `[preview]` (coarsened `cell_m`, frames, frame_px).
- `recipe/derived.py`: cell counts, actual size, fps, dt.
- `cli/main.py`: `check` and `version`; exit code 2 on recipe errors.
- Tests: valid recipe resolves with defaults; a typo (`radius_n`) fails naming `radius_m`; missing
  `size_m` fails; preview coarsening gives 48 cells on the long axis; fps = frames / duration.

### T1.3 - Device and grid

- `sim/device.py`: picks `cuda:0` or `cpu` for `--device auto|cuda|cpu`; sets
  `wp.config.deterministic` to run-to-run before any kernel module loads; errors clearly when `cuda` is
  asked for and absent.
- `sim/grid.py`: the MAC grid (face velocities `u`, `v`, `w`; centered `smoke`, `temperature`, `pressure`,
  `divergence`) and face boundary kinds, allocated on the device.
- Tests: field shapes for a 4 x 6 x 5 grid; `auto` picks CPU when CUDA is hidden.

### T1.4 - Advection

- `sim/advect.py`: semi-Lagrangian backtrace and MacCormack correction with clamping, for centered scalars
  and for each face velocity component. Trilinear sampling with boundary clamping in `sim/sample.py`.
- Tests (CPU, 16 cubed): a constant field stays constant; a blob in uniform velocity moves by `u * t`
  within a cell; MacCormack keeps a blob's peak higher than plain semi-Lagrangian after 20 steps; clamping
  never creates values outside the original range.

### T1.5 - Pressure projection

- `sim/pressure.py`: divergence, red-black Gauss-Seidel sweeps (fixed count), gradient subtraction. Closed
  faces: zero normal velocity, Neumann pressure. Open faces: pressure 0.
- Test: a random velocity field's divergence norm drops by at least 90 percent with 60 sweeps at 16 cubed;
  closed-face normal velocities are exactly 0 after projection.

### T1.6 - Emitters and noise

- `sim/noise.py`: integer hash of `(seed, emitter index, lattice cell)` and trilinear value noise, as
  `wp.func`s.
- `sim/emitters.py`: sphere and box coverage with smoothstep edge and noise breakup; the gather kernel that
  blends smoke, temperature and velocity per spec 3.3.
- Tests: smoke added over a second matches `smoke_per_s` times covered volume within 5 percent; same seed
  gives identical fields, different seed differs; nothing is emitted outside `start_s .. end_s`.

### T1.7 - Forces, dissipation and the frame loop

- `sim/forces.py`: buoyancy (spec 3.2 step 2). `sim/dissipate.py`: decay and cooling.
- `sim/stepper.py`: one substep in the spec's order, each step a named call.
- `sim/run.py`: warmup, then for each frame its substeps followed by a `capture(frame_index)` callback.
- Tests: a hot puff's smoke-weighted center rises; with no dissipation and closed faces, total smoke stays
  within 2 percent over 40 steps; with `cooling_per_s`, temperature approaches ambient.

### T1.8 - Camera and ray march

- `render/camera.py`: view basis from elevation and azimuth; the domain view rectangle and its pixel grid.
- `render/normal_field.py`: Gaussian-blurred smoke and its gradient, once per frame.
- `render/raymarch.py`: the kernel of spec 4.2, writing raw heat, thickness and normal images.
- `render/raw_frame.py`: the per-frame image record, copied to the host.
- Tests: a uniform slab of known depth gives `thickness = 1 - exp(-k s d)` within 1 percent; for a smoke
  sphere, the left edge's normal has x < 0, the top's y > 0, the center faces the camera; a hot cell
  behind a dense wall shows no heat when `smoke_hides_heat = 1` and shows it when 0; elevation 90 sees the
  top face.

### T1.9 - Sheet assembly

- `sheet/crop.py` (content, square, margin, gutter retry), `sheet/seat.py`, `sheet/resample.py`,
  `sheet/soften.py`, `sheet/quantize.py`, `sheet/pack.py`, `sheet/sheet_json.py` (incl. git-relative
  `source`), `sheet/assemble.py` (spec section 5's order).
- Tests on synthetic raw frames: the crop is square and contains all content; every frame has a 2 px
  zero gutter; a camera-facing normal quantizes to (128, 128) and up-facing to A = 255; heat's largest byte
  is 255 when any heat exists and all zero when none; sheet size is `columns * frame_px` by `rows *
  frame_px`; JSON keys are exactly the contract's, in order; `source` is repo-relative with forward
  slashes.

### T1.10 - Reports

- `report/color.py` (sRGB conversions, ramps), `report/composite.py` (spec 6.1 formula),
  `report/contact.py`, `report/channels.py`, `report/numbers.py`, `report/settings_log.py`,
  `report/timing.py`.
- Tests: composite of G = 0 is the background exactly; numbers on a synthetic sheet give the expected
  coverage, box, `peak_frame` and `fade_frame` (including `never`); `settings.toml` loads back as a recipe
  and resolves to the same values.

### T1.11 - `plume run`, preview and determinism

- `cli/run.py` wires the four pipeline steps; `cli/summary.py` prints the stdout summary.
- Tests: a tiny recipe (24 cells, 4 frames, 64 px) on CPU writes all eight files; running it twice gives
  identical bytes in all but `timing.txt`; a recipe error exits 2.

### T1.12 - The smoke puff recipe and look review

- `recipes/smoke_puff.toml`: one soft sphere puff, rising and thinning over about 3 s.
- Iterate with `--preview`, then a full run; send the user the contact sheets and channel strip; adjust
  until the user approves.
- Store `tests/golden/smoke_puff_preview.numbers.txt` and a test that compares within tolerance.
- Measure and record: preview on GPU (target under 10 s), preview on CPU (under 30 s), full run (record
  against the 60 s first-version budget).

### T1.13 - Portability and CI

- A `gpu` test: the tiny recipe on CPU and CUDA agrees within tolerance (thickness bytes within 3, normals
  within 6, `numbers.txt` values within 2 percent).
- Run the preview in WSL Ubuntu on CPU.
- `.github/workflows/ci.yml`: Ubuntu, uv, `pytest -m "not gpu"`.

### T1.14 - Docs and close

- `CLAUDE.md`: setup, commands, the iterate loop, conventions (house style, code organization, determinism
  rules), where docs live.
- `README.md`: what Plume is, install, a run, the sheet contract, Godot import settings (Lossless, mipmaps
  on, Detect 3D off).
- `tools/gen_recipe_reference.py` writes `docs/recipe-reference.md` from the schema; a test fails when it
  is stale.
- `docs/look-tuning.md`: the first entries learned in T1.12.
- Retro; pull request to `main`.

## Slice 2 - Solver quality and iteration tools (outline)

Multigrid pressure behind `pressure.solve`; vorticity confinement; curl-noise turbulence; wind and drag; the
CFL substep cap; `extends` and `--set`. Look review: the puff with turbulence, and preview against final
run looking alike.

## Slice 3 - Combustion (outline)

Fuel and flame fields, ignition, burn rate, heat and smoke per fuel, expansion as a divergence source; flame
in the heat channel. `recipes/fireball_plume.toml`, reviewed against the reference image.

## Slice 4 - Keyframed and burst emitters, ground dust (outline)

Keyframes on any numeric emitter value; `velocity_mode = "outward"` tuned for bursts; the impact dust skirt
rolling along the closed floor. `recipes/fireball_impact_dust.toml`.

## Slice 5 - Looping sheets (outline)

`loop` and `loop_blend_frames`: steady state, capture, crossfade. `recipes/building_fire.toml` and
`recipes/chimney_smoke.toml`.

## Slice 6 - Close-ups and performance (outline)

512 px frames on 4096 sheets; profiling; the 60 s default-run budget met and recorded.
