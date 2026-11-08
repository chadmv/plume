# Live viewer (design)

Date: 2026-11-08. Status: every decision chosen by the user in the design interview of 2026-11-08 (rounds 1 and 2,
Q1 to Q18, all recommended, plus the user's navigation request in Q10); this document is the detail for review.
Adds amendment A5 to the design brief (section 11). Tracked by
`docs/backlog/feature-2026-11-07-live-interactive-simulation-viewer.md`.

## Plain version

`plume view recipe.toml` opens a window on the PC that runs the recipe on the GPU and shows the smoke in 3D while
it simulates. A frame lands about every 36 ms on the 2080 Ti, so the whole smoke puff appears in about 3 seconds.
The run then loops. You can scrub, pause and step it, and you can fly around it or into it at any frame. It is
drawn by the same kernel that draws the sheet, with the same look formula, so the viewer and the sheet can never
disagree about how the smoke looks.

Save the recipe (you, or Claude from a chat) and the viewer re-runs it. Drag a value in the viewer's panel and
it re-runs when you let go; Save writes the change back into the recipe and keeps its comments. A Compare key
flips to the run before at the same frame and angle. A second tab plays the finished flipbook on a card, the way
a game will show it. Under the view, curves of the run's numbers show where the smoke peaks and fades.

`plume run` is unchanged: the sheet still comes only from a batch run of the saved recipe, with the same bytes as
before.

## 1. Why

The sheets and contact sheets show 64 still images from one fixed angle. They hide the three things that most
decide whether a simulation is right: motion (does the puff billow, or drift, or pop), depth (is it a ball or a
flat card), and the inside (is the solver smearing a curl, or is the render hiding it). The user's words: "it
needs an application to view the live simulation in order to properly judge the simulation results. Just judging
the sheets is not enough."

The GPU makes this cheap. On the 2080 Ti the full smoke puff (80 x 100 x 80 cells, 64 frames, 203 steps)
simulates in 2.3 s and ray marches all 64 frames in 0.16 s (`docs/retros/2026-11-08-shade-channel-layout.md`).
The cloud CPU takes about 10 minutes for the same run, so the viewer is a GPU tool; the CPU path works but is
slow, and cloud sessions have no screen.

## 2. Decisions

Numbered V1 to V18 after the interview questions Q1 to Q18.

### What it is (round 1)

- **V1 - Purpose: watch, follow edits, edit.** The viewer plays a run in motion from any angle; re-runs when the
  recipe or a parent on disk changes; and has a panel to change recipe values and save them. A chat drives it by
  editing the recipe file, which the viewer follows. An MCP server is deferred (section 13).
- **V2 - Two tabs over one viewport.** **Volume** draws the simulated fields live with Plume's own ray march,
  lit and colored by the contact-sheet formula and the recipe's `[look]` ramps, over a background, from any
  camera. **Sheet** plays the assembled flipbook on a camera-facing card at the sheet's fps, looping, as a game
  shows it. `Tab` switches.
- **V3 - A live run, then playback.** A run shows each frame as it lands; the playhead follows the newest frame,
  and the timeline shows how far the run has got. Once done, the run loops. Controls: play and pause (`Space`),
  step a frame (`,` and `.`), first and last frame (`Shift+,` and `Shift+.`), speed 1/4x, 1/2x, 1x and 2x of
  effect time, loop on or off, and a scrub bar. Each frame's fields are kept on the GPU (section 4).
- **V4 - Camera and guides.** Orthographic by default, with a perspective toggle (`P`). The **sheet camera**
  (`Home`) is the recipe's `camera.elevation_deg` and `azimuth_deg`, orthographic, framed like the sheet's crop.
  Guides (toggle `G`): the domain box with closed faces solid and open faces dashed, 0.5 m ticks along the floor
  edges, each emitter's outline (sphere or box, dashed while the emitter is off), and the light direction as an
  arrow. Navigation is V10.
- **V5 - Views and inspection.** View buttons **Look**, **Heat**, **Thickness** and **Shade** (**Normal** in the
  normal layout), keys `1` to `4`: the sheet's channels, drawn live from any angle. A **numbers strip** under the
  viewport plots coverage, mean thickness and peak heat per frame with the playhead, and marks frames where smoke
  reaches an open face or the ceiling, or where the step cap added steps. A **slice plane** (`L` to cycle off,
  x, y, z; drag it along its axis with the left mouse) colors one field: smoke, temperature, speed or swirl
  (vorticity magnitude).
- **V6 - Grid.** The recipe's full grid by default. A **Preview** toggle runs the `[preview]` grid instead, for
  close-up recipes too big to re-run quickly.
- **V7 - Technology.** Python in the same process as Plume: the viewer imports Plume's simulation and renderer,
  runs them on the GPU with Warp, and shows them in a Dear ImGui window through imgui-bundle (1.93.0: Python 3.13
  wheels for Windows, Linux and macOS, with ImPlot). Each viewport image is uploaded as an OpenGL texture
  (PyOpenGL) and drawn as an ImGui image. An optional extra, `view`, so `plume run`, the tests that
  need no window, and CI keep today's dependencies.
- **V8 - Same simulation as `plume run`.** The viewer runs the same stepper, step cap and seed through the same
  code path (section 3.1), so frame 30 in the viewer is the field frame 30 of the sheet came from. A test proves
  it (section 9).
- **V9 - Command and amendment.** `plume view RECIPE [--device auto|cuda|cpu] [--preview] [--set key=value ...]`
  opens a recipe; `plume view OUT_DIR` (a folder holding a sheet and its JSON) opens the Sheet tab only, with no
  simulation and no GPU needed. The brief's "headless and command-line only; no window" becomes amendment A5
  (section 11).

### How it behaves (round 2)

- **V10 - Navigation: Maya plus Unreal fly.** The user asked for Maya's viewport controls and Unreal's WASD fly
  "the way Petri has it". Petri (`chadmv/petri`, its `godot/README.md` camera table and
  `src/ui/camera_motion.cpp`) holds the right mouse button for a captured free-look, flies with WASD and E/Q,
  trims the speed with the wheel, and eases the speed in and out. Plume re-implements that behavior in Python; it
  shares no code with Petri.

  | Input | Does |
  |---|---|
  | Alt + left drag | Tumble around the pivot |
  | Alt + middle drag | Track (pan) |
  | Alt + right drag | Dolly toward or away from the pivot; in orthographic, change the view's size |
  | Wheel | Dolly in steps (orthographic: change the view's size) |
  | F | Frame the smoke of the current frame; Shift+F frames the whole domain box |
  | Right mouse held | Free-look with the cursor captured; the eye stays put |
  | Right mouse + W, A, S, D | Fly forward, left, back, right along the view |
  | Right mouse + E, Q | Fly straight up, down |
  | Right mouse + wheel | Trim the fly speed, x1.25 a notch, shown on screen while it changes |
  | Home | The sheet camera (orthographic) |

  Plain left click and drag never move the camera; they belong to the slice plane, the light arrow (V11's
  render keys) and the panels. Fly speed eases toward its target with a short time constant (Petri's 25 ms
  rising, 35 ms falling are the starting values) and is one domain width per second at a trim of 1, so a 2 m
  puff and a 20 m fire feel alike. Releasing the right button puts the pivot on the smoke under the screen's
  center (the first point along that ray where thickness passes one half), or on the domain's center if the ray
  finds none. The first fly key in an orthographic view switches to perspective, since flying forward in
  orthographic changes nothing visible; `Home` goes back. Pitch is clamped to about 88 degrees either side, as in
  Petri.
- **V11 - Stages: what re-runs and what redraws.** Each recipe table carries a stage, once, in the schema (a
  `stage` on the field's metadata, so a key inherits its table's stage; top-level `seed` carries its own):
  - **simulation**: `seed`, `[domain]`, `[time]`, `[[emitter]]`, `[forces]`, `[dissipation]`, `[solver]`, and
    `[combustion]` when slice 3 adds it; `[preview]` also counts as simulation while the Preview toggle is on.
    A change re-runs from time 0.
  - **render**: `[render]`. A change redraws from the kept fields; no re-run. The light volume is recomputed for
    each drawn frame.
  - **look**: `[look]`. Redraws only.
  - **sheet**: `[output]`, `[camera]`. Re-assembles the Sheet tab from the kept frames; in the Volume tab only
    the sheet camera moves.

  A dragged simulation value starts its re-run when the drag ends (or on Enter after typing), not on every pixel
  of the drag. A new simulation edit during a re-run cancels it and starts again. A re-run replaces the old
  frames as it goes, with the playhead on the newest frame. The editing panel's "redraw only" labels and the
  recipe reference read the same stage.
- **V12 - Compare (A/B).** The viewer keeps the run before the latest one (B). `C` or the Compare button flips the
  viewport between A and B at the same frame and camera; **Split** shows them side by side with one camera. The
  panel lists the keys that differ between A and B. A re-run makes the current run B and the new one A.
- **V13 - The editing panel.** Every key of the resolved recipe, grouped by table, with its unit and the schema's
  description as a tooltip. Defaults are dimmed, keys the recipe sets are plain, keys changed in the viewer are
  highlighted, each with a Reset; **Revert** resets them all. Numbers are drag fields (Ctrl + click to type) with
  a drag step of about 1 percent of the value's size per pixel (a fixed small step for a value of 0), since the
  schema has no ranges; vectors are three fields; text keys with choices are drop-downs; booleans are checks.
  Keyframed values, ramps and colors are shown read-only; they are edited in the file in this version. Every
  edit is checked by the same rules as `plume check` before it is applied, and a rejected edit shows the check's
  message beside the field.
- **V14 - Save and reload.** **Save** (`Ctrl+S`) writes only the changed keys into the opened recipe, keeping its
  comments, order and layout (tomlkit). A key whose value comes from an `extends` parent is written into the
  opened recipe as its own override, never into the parent, which other recipes may share. An emitter is found
  by its `name`. `--set` values from the command line start as edits, so Save can write them in. The viewer
  watches the opened recipe and every parent in its `extends` chain (polling their modification times four
  times a second; no watcher dependency). When one changes, the viewer reloads and checks it, then re-runs or
  redraws by stage. Unsaved viewer edits are applied on top of the reloaded file, and a banner says how many.
  A recipe error on reload leaves the last good run playing and shows the message `plume check` would print in
  a red banner; nothing re-runs until the file is fixed.
- **V15 - Clips and stills.** **Save clip** writes the current view (camera, view button, tab, background, A or
  B) playing through every frame as an animated PNG at the sheet's fps; **Save still** (`F12`) writes the
  current frame as a PNG. Both go to `out/<name>/view/` (or the `--out` folder's `view/`), named by recipe,
  frame and a counter, each with a small `.toml` beside it naming the camera pose, frame, view, and the
  resolved recipe values, so the view can be reproduced and a thread can read exactly what the user saw. A
  headless clip command is deferred (section 13).
- **V16 - The look review moves to the viewer.** The look-tuner still runs `plume run`; sheets, contact sheets,
  `numbers.txt` and the golden file stay the written record and what tests compare. The thread asks the user to
  judge in the viewer: its message gives the command to run on the PC (`uv run plume view recipes/<name>.toml`)
  and what to look at, and the user's verdict is given as today. A thread that launches the viewer on the PC
  itself (a Remote Control session) is making a headed GPU run and takes the PC slot through the coordinator; a
  user launching it needs no queue. `docs/agent-orchestration.md` (stage 6) and
  `.claude/agents/look-tuner.md` gain this step in slice V1.
- **V17 - Speed targets.** On the 2080 Ti with the smoke puff's full grid and the window at 1600 x 900: at least
  30 redraws a second while orbiting or flying (the viewport may draw at half resolution while the camera moves
  and refines to full within a quarter second of stopping); a whole re-run, frames appearing as they land, in
  under 4 s. The viewer shows its redraw time and the run's time in a corner. Measured in slice V1; a target
  that is missed goes back to the user, not quietly lowered.
- **V18 - Build order.** Three slices, each ending with the user's look at it on the PC (section 10). V1 runs
  alongside Plume slice 3 (combustion), so slice 3's fireball can be judged in the viewer.

## 3. How the run works

### 3.1 One frame loop for both commands

`sim/run.py`'s `simulate(recipe, derived, device, capture)` becomes a thin loop over a generator,
`simulate_frames(recipe, derived, device)`, which runs warmup and then yields `(frame_index, grid)` after each
frame's block of steps; the step log is its return value. `plume run` and the viewer both iterate it, so there is
one frame loop. The viewer advances it one frame per window update during a run (about 36 ms at the puff's grid
on the GPU), which keeps the window responsive without a second thread: Warp kernels and the window's drawing
share one thread and one CUDA stream, and a cancelled run is simply a generator that is dropped.

### 3.2 What a frame keeps

At each yielded frame the viewer:

1. Renders the frame from the sheet camera exactly as `plume run` does (the raw 2D frame of amendment A1) and
   keeps it, so the Sheet tab, the numbers strip and the heat and shade divisors come from the normal assembly
   and report code after the run.
2. Copies the fields the views read into the frame cache: smoke and temperature (and fuel and flame when slice 3
   adds them) for the Volume tab, and the three velocity components for the slice plane's speed and swirl.

### 3.3 The frame cache

Fields are kept on the GPU as 16-bit floats. Per frame of the smoke puff: 640,000 cells, about 1.3 MB a field;
with smoke, temperature and velocity, about 6.4 MB, or about 410 MB for 64 frames, and twice that with the B run
of V12. The cache has a budget (`--cache-gb`, default 4). When a run would not fit, the viewer first drops
velocity (the slice plane then offers smoke and temperature only), then keeps every second, then every fourth
frame, and says so in the status line. Frames it did not keep are skipped in playback, never interpolated.

## 4. Drawing the viewport

### 4.1 The ray march with any camera

The ray march kernel (`render/raymarch.py`) today casts parallel rays from the sheet camera's plane. It gains a
camera input that is either orthographic (an origin plane and one direction, as now) or perspective (an eye and a
per-pixel direction), and reads 16-bit cached fields as well as the live 32-bit grid. The march itself (fixed
half-cell steps, trilinear samples, Beer-Lambert thickness, heat hidden by smoke, the shade sum) is unchanged.
For the sheet camera the kernel's output must stay byte-identical to today's (section 9), so the sheet and the
same-bytes and golden tests are untouched.

### 4.2 Light, heat and shade in the viewport

- **The light stays put in the world.** `render.light_dir` is in the sheet camera's space; the viewer turns it
  into world space once, so orbiting shows the smoke lit from the same side as the sheet, and the guide arrow
  points along it. Dragging the arrow with the left mouse changes `render.light_dir` as an edit (a render-stage
  key, so it redraws).
- **The light volume** is computed per drawn frame from the cached smoke (on the GPU it costs nothing visible) and
  reused while the camera moves; it is recomputed when the frame, the light or a render key changes.
- **Heat** is divided by the run's heat divisor (the sheet's, from section 3.2); during a live run, by the
  largest divisor of the frames so far.
- **Shade** in the Volume tab is the raw shade of the march (the shade sum over thickness), with the run's shade
  divisor once the run finishes. The sheet's thin-pixel easing is a 2D pass on the sheet image; it shows in the
  Sheet tab, not in the volume.
- **Look** uses the contact sheets' composite formula and `[look]` ramps, in linear light, then converts to sRGB
  for the screen. Backgrounds: the recipe's neutral and grass colors, plus a dark gray, cycled with `B`.

### 4.3 The rest of the viewport

- Guides are lines drawn with ImGui's draw list after projecting their 3D points with the viewer camera: the
  domain box, floor ticks, emitter outlines and the light arrow. No mesh rendering.
- The **slice plane** is a 2D gather kernel that samples one cached field on the plane at the viewport's
  resolution and maps it through a fixed color ramp, with a legend of its range; it is drawn over the volume with
  the volume dimmed behind it.
- The **Sheet tab** draws the assembled sheet's current cell on a card facing the camera, sized by `frame_m` and
  seated at the JSON's `seat` point, over the chosen background, with the contact-sheet composite. Playback
  steps whole sheet frames at the sheet's fps; no blending between frames.
- While the camera moves, the volume may be drawn at half the viewport's resolution and scaled up, then redrawn
  at full resolution a quarter second after the camera stops.

## 5. The window

- **Top bar:** recipe path, the Volume and Sheet tabs, the view buttons, Slice, Guides, Full or Preview, the
  device, the Compare and Split buttons.
- **Viewport:** the camera mode (Ortho or Persp), frame number and effect time, and, while a fly speed is being
  trimmed, the trim.
- **Right panel:** the editing panel (V13), Save, Revert, the re-run status with a progress bar, and the A/B
  differences.
- **Bottom:** the transport (V3), the scrub bar showing how far the run has got, and the numbers strip (V5).
- **Banners** over the viewport for recipe errors, unsaved edits kept over a reload, and a thinned frame cache.

The interview's mockup, `2026-11-08-live-viewer-mockup.png` beside this spec, shows the layout; it is a sketch,
not a pixel spec (its smoke is a real frame of the smoke puff preview).

## 6. Files

A new feature folder, `src/plume/view/`, one responsibility per file, with tests under `tests/view/`:

| File | Holds |
|---|---|
| `app.py` | the window and its update loop: input, layout, drawing the panels |
| `session.py` | the opened recipe, its edits, the A and B runs, what a change re-runs or redraws (V11) |
| `live_run.py` | iterating `simulate_frames`, sheet-camera captures, cancelling |
| `frame_cache.py` | 16-bit field storage, the budget and frame thinning |
| `navigation.py` | the camera state and the Maya and fly rules, as pure math with no window |
| `viewport.py` | drawing a frame: march, light volume, half-resolution while moving, texture upload |
| `guides.py` | projecting and drawing the domain box, ticks, emitters and the light arrow |
| `slice_plane.py` | the slice kernel and its ramp |
| `sheet_player.py` | the Sheet tab's card |
| `recipe_writer.py` | writing changed keys into a recipe with tomlkit (V14) |
| `recipe_watch.py` | polling the recipe and its parents |
| `capture.py` | clips and stills with their `.toml` |

Changes outside it: `sim/run.py` (section 3.1), `render/raymarch.py` and `render/frame_renderer.py` (section 4.1),
`recipe/schema.py` (stages), `cli/main.py` (the `view` command), `pyproject.toml` and `uv.lock` (the `view`
extra), `README.md` (install and controls), `CLAUDE.md` (the command and when to use it), and the two agent docs
of V16.

`plume view` without the `view` extra installed exits 1 with the line that installs it (`uv sync --extra view`).

## 7. Dependencies

The `view` optional extra (`[project.optional-dependencies]`), pinned in `uv.lock` like Warp: `imgui-bundle==1.93.0`, `PyOpenGL==3.1.10`,
`tomlkit==0.15.2`. Animated PNGs come from Pillow, which Plume already uses.

## 8. Determinism

- `plume run`'s outputs keep their bytes: the frame-loop refactor and the camera input of the ray march change
  no number in a sheet run (section 9).
- The viewer's simulation is `plume run`'s simulation, frame for frame. The viewer as a whole (window timing,
  redraw resolution, cache thinning) is not held to same bytes, and nothing it shows is a deliverable: the sheet
  comes from `plume run` of the saved recipe.
- Saved recipes are plain recipes; a recipe saved by the viewer runs the same as one written by hand.

## 9. Tests

All run on CPU at tiny grids and need no window, so they run in CI and cloud sessions; CI installs the `view`
extra.

- **Same frames:** for a small recipe, every sheet-camera frame the viewer captures is byte-identical to `plume
  run`'s raw frame, and its cached 16-bit smoke equals the run's smoke rounded to 16 bits.
- **Sheets unchanged:** the existing same-bytes and golden tests pass untouched, and a new test pins one raw frame
  of the small recipe against a stored digest taken before the ray march change.
- **Stages:** every schema table and top-level key has a stage (a new table without one fails the test); each
  stage triggers only its own work in `session.py` (a render edit never re-runs).
- **Navigation:** tumble, track and dolly directions; free-look keeps the eye; each fly axis and the speed's
  easing; Home returns the sheet camera exactly; the first fly key switches to perspective; the pitch clamp.
- **Recipe writer:** comments, blank lines and order survive a save; a key from a parent is written into the
  child; an emitter is found by name; the saved recipe loads and resolves to the edited values; writing
  nothing changes no byte.
- **Reload:** a recipe error keeps the last run and reports `plume check`'s message; unsaved edits survive a
  reload; a parent's change is seen.
- **Frame cache:** the budget drops velocity first, then thins frames, and reports it.
- **Ray march cameras:** a perspective camera with a narrow field at a far distance matches the orthographic
  image within a small tolerance; the slice kernel samples a known field exactly.
- **Capture:** a clip has one image per kept frame at the sheet's fps; its `.toml` reloads to the same camera.
- **On the PC, by hand:** the window opens, the controls of V10 work, and the speed targets of V17 hold; recorded
  in the slice's retro.

## 10. Build slices

Each slice gets its own task plan from the slice-planner and ends with the user trying it on the PC.

1. **V1 Watch.** The frame-loop refactor; the ray march camera input; `plume view RECIPE`; the window with the
   Volume tab, live run and playback; the frame cache; navigation (V10); guides; the Look, Heat, Thickness and
   Shade views; the recipe watch with error banners; the agent-doc updates of V16; speed measured against V17.
   Done when the user can judge a run of the smoke puff in motion from any angle, re-running on save.
2. **V2 Tune.** Stages in the schema; the editing panel; Save with tomlkit; A/B compare and split; the light
   arrow drag. Done when a value dragged in the viewer and saved gives the same look through `plume run`.
3. **V3 Inspect.** The Sheet tab and `plume view OUT_DIR`; the numbers strip; the slice plane; clips and stills.
   Done when the user has judged one recipe's sheet in the Sheet tab and saved a clip a thread read back.

## 11. Amendment to the brief

- **A5 - A window for judging (changes "Constraints confirmed": "Headless and command-line only; no window").**
  `run` and `check` stay headless and their outputs are unchanged. `view` is an optional window for watching and
  tuning, installed with the `view` extra. Agreed by the user 2026-11-08.

## 12. Rejected alternatives

- **A browser page with a WebGL volume renderer.** A second renderer to keep in step with the sheet's, plus a
  server; the viewer would show a look the sheet does not have.
- **Polyscope, PyVista or VTK.** Ready-made, but they draw volumes their own way (isosurfaces, transfer
  functions), not Plume's soft smoke; VTK is a heavy dependency.
- **Godot.** Ties Plume to a game engine, and to its first consumer's; Plume stays generic.
- **An MCP server in the first version.** Saving the recipe file already lets a chat drive the viewer.
- **The preview grid by default.** Judging a coarser cloud than the sheet ships.
- **Re-running on every pixel of a drag.** A run takes seconds; it would restart constantly.
- **Writing edits into an `extends` parent.** Other recipes may share it.
- **A simulation thread beside the window's.** Two threads launching Warp work on one device need stream and
  lock rules; one frame per window update keeps the window responsive at the puff's grid without them.
- **Blending between sheet frames in the Sheet tab.** A game may or may not blend; the tab shows the frames as
  they are.

## 13. Deliberately deferred

- An MCP server for chat-driven tuning (the backlog item's original proposal):
  `docs/backlog/idea-2026-11-08-viewer-mcp-server.md`.
- A headless clip command (`plume view --clip`) usable from a cloud session:
  `docs/backlog/idea-2026-11-08-headless-viewer-clips.md`.
- Editors for ramps, colors and keyframed values in the panel.
- Motion vectors, frame blending, and a game-shader preview beyond the contact-sheet formula in the Sheet tab.

## 14. Risks

- **One thread for simulation and window.** A grid much bigger than the puff's makes each frame's block of steps
  longer than a window update, so the window stutters during a run. The Preview toggle is the answer for now; a
  simulation thread is the fallback if slice 6's close-ups need it.
- **imgui-bundle, PyOpenGL and Warp in one process on Windows.** Untested together. The first task of V1 is a
  spike: a window showing one Warp-rendered image, timed on the PC.
- **tomlkit edge cases.** Inline tables (`noise = { ... }`) and arrays of tables (`[[emitter]]`) must round-trip;
  the recipe writer tests cover both, on the example recipes as they are.
- **The ray march change.** A camera input in the sheet's kernel could move a sheet's bytes; the digest test of
  section 9 catches it.
