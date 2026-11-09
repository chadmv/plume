# Live viewer slice V1 Watch plan

Date: 2026-11-08. Builds slice V1 of `docs/specs/2026-11-08-live-viewer-design.md` (section 10, item 1),
tracked by `docs/backlog/feature-2026-11-07-live-interactive-simulation-viewer.md`. The design is settled
(the user's picks V1 to V18, merged in PR #12), so this goes straight from intake to plan.

Done when the user can judge a run of the smoke puff in motion from any angle on the PC, re-running on save.

## Scope

In V1: the frame-loop generator; the ray march camera input; `plume view RECIPE`; the window with the Volume
view, the live run and playback (V3); the frame cache (V3.3); navigation (V10); guides (V4); the Look, Heat,
Thickness and Shade (Normal) views (V5's buttons); backgrounds; the recipe watch with error banners (V14's
reload half); the Full or Preview toggle (V6); the redraw and run times (V17); the agent-doc step of V16.

Left to V2 and V3 as section 10 says: stages in the schema, the editing panel, Save, Compare and Split, the
light arrow drag, the Sheet tab and `plume view OUT_DIR`, the numbers strip, the slice plane, clips and
stills.

## Corrections to inputs

- **No velocity in V1's frame cache.** Section 3.2 caches the three velocity components for the slice plane,
  which is V3. V1 keeps smoke and temperature only, so the budget's "drop velocity first" step arrives with
  the slice plane; V1's budget only thins frames.
- **The march reads 32-bit fields only.** Section 4.1 has the ray march read 16-bit cached fields directly.
  Warp kernels are typed by their arrays' dtype, so that would mean a second copy of the march (and of the
  light volume and trilinear sampler) for `float16`. Instead the viewer widens one cached frame into 32-bit
  scratch arrays with a small cast kernel each time the drawn frame changes (two 2.6 MB copies at the puff's
  grid), and the one march kernel stays the only march. The cache is still 16-bit.
- **The look composite runs as a Warp kernel in the viewer.** Measured on the cloud CPU (4 cores), the
  report's numpy composite plus sRGB takes 50 ms for an 800 x 450 image and 228 ms at 1600 x 900, far from
  V17's 30 redraws a second. The viewer composites on the device instead. To keep one definition of each
  piece: the ramps and the sRGB curve are tabulated from `report/color.py`'s own `ramp` and
  `linear_to_srgb` (the kernel interpolates the tables); only the two composite lines (`light = ...`,
  `color = background * (1 - G) + ...`) are written twice, in `report/composite.py` and the kernel, and a
  test holds them equal (`test_look_kernel_matches_report_composite`). A game shader is a third copy of the
  same lines by design.
- **Heat and shade divisors.** The sheet's divisors come from assembling the run (resample, soften, ease),
  which takes 2.3 s on the GPU puff run, all host numpy. The viewer assembles on a worker thread once a run
  finishes (host code only: no Warp work leaves the window's thread, keeping section 3.1's rule) and swaps
  in the sheet's divisors when it lands. Until then heat uses the largest raw heat of the sheet-camera
  frames so far (the spec's "largest divisor of the frames so far", before softening) and shade uses 1.
- **Home frames the sheet's crop once it is known.** Before the assembly lands, Home frames the sheet
  camera's whole domain view.
- **The GL texture upload lives in `app.py`.** Section 6 puts it in `viewport.py`; keeping OpenGL out of
  `viewport.py` lets every drawing test run with no window. `viewport.py` returns an RGBA8 image.
- **The guide box's dashes are per edge.** An edge is shared by two faces; it is drawn solid when either of
  its faces is closed and dashed when both are open, so a closed floor under open sides reads as a solid
  floor outline with dashed walls.
- **`glfw` joins the `view` extra.** Capturing the cursor for the right-mouse free-look needs GLFW's input
  mode, which imgui-bundle reaches through the `glfw` package (`imgui_bundle.glfw_utils`; imgui-bundle points
  it at its own GLFW library). `tomlkit` (section 7) waits for V2's Save.
- **The first fly key goes to perspective; Home goes back to orthographic.** As written. Switching keeps the
  view's size at the pivot: `distance = half_height / tan(fov / 2)` and back. The field of view is 40
  degrees, vertical.
- **Fly trim bounds.** The spec gives the notch (x1.25) but no bounds; V1 uses 1/8 to 8.

## Measurements

- **Window in the cloud.** imgui-bundle 1.93.0 and PyOpenGL 3.1.10 install from wheels on Linux; a 31-frame
  hello_imgui run uploading a numpy image as a texture each frame runs under `xvfb-run` with Mesa's software
  GL. So the window can be smoke-tested in cloud sessions; it is not a test (CI has no display).
- **Composite cost** (above): numpy 50 ms at 800 x 450, 228 ms at 1600 x 900; the same composite through
  lookup tables 11 and 51 ms. Probe: random heat, thickness and shade at both sizes, five passes each.
- **Raw frame digests before the march change** (base 626d5d9, Linux CPU): the base test recipe with
  `temperature_k = 900`, camera elevation 20, azimuth 30, last of 4 frames, (68, 66, 5) float32:
  shade layout `9a79a4ed...492f334`, normal layout `8e2bf095...9e121dc9711f` (full hashes in the test). The
  PC runs the same probe at the base commit before its gate; if Windows CPU gives other bytes, its digests
  are added beside these, keyed by platform.

## Tasks

The build is done by the orchestrator in this thread, in order; the code-reviewer reviews in three groups
(T1 to T3, T4 to T8, T9 to T11) and the verifier gates the end. Commits: one per task.

### TV1.1 - Frame loop generator (kernel)

- `sim/run.py`: `simulate_frames(recipe, derived, device)` runs warmup, then yields `(frame, grid)` after
  each frame's block; its return value is the `StepLog`. `simulate(..., capture)` becomes a loop over it.
- Tests (`tests/sim/test_frame_loop.py`): the generator yields frames 0 to n-1 in order and returns the same
  `StepLog` as `simulate`; the existing frame-loop, same-bytes and golden tests pass untouched.

### TV1.2 - Ray march camera input (kernel)

- First, `tests/render/test_raw_frame_digest.py` pinning the two digests above (it passes at the base).
- `raymarch.py`: `ViewParams` gains `perspective` (0 or 1) and `eye`. Orthographic is today's code
  path unchanged; perspective casts from `eye` along `normalize(right * x + up * y - toward)`, where x and y
  are the pixel's coordinates on the plane one meter in front of the eye, and starts at the eye when it is
  inside the domain.
- `frame_renderer.py`: the march launch becomes `march_fields(smoke, temperature, info, view, image)` on
  the renderer, used by `render(grid)` and the viewer; `toward_light_world(camera, light_dir)` is the one
  place the sheet camera's light turns into world space. `light_volume.py`: `compute` takes the smoke array
  and cell size, not the grid.
- Tests: the digests hold; a perspective camera with a 1 degree field 200 m away matches the orthographic
  image of the same view within a small tolerance (measured and recorded in the test); an eye inside a
  uniform smoke box sees thickness `1 - exp(-k * d)` to the far wall.

### TV1.3 - `plume view` and the `view` extra (pipeline)

- `pyproject.toml`: `[project.optional-dependencies] view = ["imgui-bundle==1.93.0", "PyOpenGL==3.1.10",
  "glfw==2.10.0"]`; `uv.lock`; CI installs `--extra view`.
- `cli/main.py`: `plume view RECIPE [--device] [--preview] [--set ...] [--cache-gb 4]`. A folder argument
  exits 64 saying the Sheet tab comes in a later slice. Without the extra, exit 1 with
  `uv sync --extra view`. Recipe errors at open exit 2 like `run`.
- Tests (`tests/cli/test_view_command.py`): parsing; the missing-extra message (import blocked); a folder is
  refused; a bad recipe exits 2 before any window.

### TV1.4 - Frame cache (view, kernel)

- `view/frame_cache.py`: per kept frame, smoke and temperature as `float16` device arrays (a cast kernel),
  a stride chosen before the run from `--cache-gb` (1, 2, 4, ... until the kept frames fit), `load(frame)`
  widening into 32-bit scratch arrays, and a note for the status line when thinned.
- Tests: stored smoke equals the source rounded to float16 (`numpy.astype(float16)`); the stride for a
  budget; frames off the stride are not kept and `nearest_kept` steps back to a kept one.

### TV1.5 - Live run (view)

- `view/live_run.py`: `LiveRun(recipe, derived, device, cache)` iterates `simulate_frames` one frame per
  `advance()`, renders each frame's sheet-camera raw frame through `FrameRenderer` exactly as `plume run`
  does, stores fields in the cache, tracks the provisional heat divisor, and after the last frame starts the
  sheet assembly on a worker thread (divisors, crop). Cancelling drops the generator.
- Tests ("same frames", section 9): for the base recipe on CPU, every raw frame equals `plume run`'s raw
  frame byte for byte, and every cached smoke equals the run's smoke rounded to float16; the assembled
  divisors equal `assemble`'s on the same raw frames.

### TV1.6 - Navigation (view)

- `view/navigation.py`: the camera state (pivot, yaw and pitch in degrees, eye distance, orthographic
  half-height, perspective flag, fly trim and velocity) and pure rules: tumble, track, dolly, wheel, frame,
  free-look, fly with eased speed, trim, release-pivot, Home; `view_camera(width, height)` gives the basis,
  eye and plane rectangle that the march and the guides share, with `project(point)`.
- Tests (section 9's list): tumble, track and dolly directions; free-look keeps the eye; each fly axis and
  the speed's easing (rise 25 ms, fall 35 ms, exact exponential); Home returns `make_camera`'s basis exactly;
  the first fly key switches to perspective; the pitch clamp at 88 degrees; the release pivot lands on the
  first point past half thickness, else the domain center; switching projection keeps the size at the pivot.

### TV1.7 - Viewport drawing (view, kernel)

- `view/viewport.py`: draws one cached frame for a view camera: widen the frame, compute the light volume
  (kept while the frame and light are unchanged), march, then a look kernel turns the raw image into RGBA8 by
  view: Look (the composite over the background, sRGB), Heat, Thickness, Shade as gray bytes, Normal as
  `(n + 1) / 2`. Half resolution while the camera moves, full within 0.25 s of stopping.
- Tests: `test_look_kernel_matches_report_composite` (bytes within 1 of `to_srgb_bytes(composite(...))` over
  a grid of heat, thickness and shade values, both layouts); a drawn frame of a sphere of smoke is opaque at
  its center and the background at the corners; gray views equal the byte formula.

### TV1.8 - Guides (view)

- `view/guides.py`: world-space segments for the domain box (dash rule above), 0.5 m ticks along the floor
  edges at multiples of 0.5 m, each emitter's outline (a sphere as three circles, a box as its edges; dashed
  when the frame's effect time is outside `start_s` to `end_s`), and the light arrow; clipping a segment to
  the near plane; dashes split in screen space.
- Tests: box edges and dash flags for a closed floor; tick positions; emitter dashed outside its window;
  a segment behind the eye is clipped.

### TV1.9 - Recipe watch and session (view)

- `view/recipe_watch.py`: the opened recipe and its `extends` parents as resolved paths, polled for
  modification times four times a second.
- `view/session.py`: opens the recipe (with `--preview` and `--set`), owns the live run, reloads on a
  change: an unchanged resolved recipe does nothing; a changed one starts a new run; a recipe error keeps
  the last run and holds `plume check`'s message for a red banner. The Full or Preview toggle reopens with
  the other grid.
- Tests: a parent's change is seen; an error keeps the last run with the message `plume check` prints; a
  comment-only edit does not re-run; a fixed recipe re-runs.

### TV1.10 - The window (view)

- `view/app.py`: hello_imgui window (1600 x 900): top bar (recipe path, views 1 to 4, Guides, Full or
  Preview, background, device, Ortho or Persp), the viewport image with guides drawn by the ImGui draw list,
  the transport (Space, `,` `.`, Shift+`,` Shift+`.`, speed 1/4x to 2x, loop, scrub bar showing the run's
  progress), banners, and the redraw and run times in a corner. One frame of the live run per window update.
  Input: V10's table; RMB captures the cursor through GLFW.
- Check: a scripted smoke run under `xvfb-run` in the cloud (opens, runs the base recipe on CPU, plays,
  exits); the real check is on the PC (TV1.12).

### TV1.11 - Docs (orchestrator)

- `README.md` (install the extra, `plume view`, the controls), `CLAUDE.md` (the command and when to use it),
  `docs/agent-orchestration.md` (stage 6 asks the user to judge in the viewer; the `view/` folder's owners),
  `.claude/agents/look-tuner.md` (the review message gives the `plume view` command), the backlog item's
  progress.

### TV1.12 - On the PC (verifier, by hand)

- `uv sync --extra view`, `uv run pytest` (gpu tests included), the digest probe at the base commit.
- `uv run plume view recipes/smoke_puff.toml`: the window opens, the controls of V10 work, the run plays;
  V17 measured at 1600 x 900: redraws a second while orbiting and flying, and the whole re-run time. A
  missed target goes back to the user. Recorded in the retro.
- The user's look at it on the PC ends the slice.
