# Live viewer slice V3 Inspect plan

Date: 2026-11-09. Builds slice V3 of `docs/specs/2026-11-08-live-viewer-design.md` (section 10, item 3),
tracked by `docs/backlog/feature-2026-11-07-live-interactive-simulation-viewer.md`. The design is settled
(V2, V5, V9, V15, sections 3.3, 4.3 and 6, merged in PR #12); V1 Watch (PR #13) and V2 Tune (PR #14) are
merged, so this goes straight from intake to plan.

Done when the user has judged one recipe's sheet in the Sheet tab and saved a clip a thread read back.

## Scope

In V3: the Sheet tab (`Tab`) and `plume view OUT_DIR`; the numbers strip; the slice plane (`L`) with smoke,
temperature, speed and swirl; velocity in the frame cache, dropped first when the budget is short; clips
and stills (`F12`, Save clip) with their `.toml`; `--out` for `plume view`.

Still deferred (spec section 13): the headless clip command, the MCP server, ramp and color editors.

## Corrections to inputs

- **Velocity is kept at cell centers**, as one 16-bit vector per cell (`wp.vec3h`, 6 bytes), not as the
  three staggered face arrays: speed and swirl are both read at cell centers, and the centering is the
  simulation's own `center_velocity_kernel`. Per frame of the smoke puff that is 3.8 MB of velocity beside
  2.6 MB of smoke and temperature, the 6.4 MB section 3.3 counts.
- **The slice plane's field is prepared per drawn frame** as one 32-bit scalar volume (smoke, temperature,
  speed `|v|`, or swirl `|curl v|` with the simulation's `curl_kernel`), and its legend's range is that
  volume's range over the whole frame (0 to the largest value; temperature from its smallest), so the
  legend stays put while the plane is dragged. The plane is drawn opaque where a pixel's ray meets it inside
  the domain; elsewhere the volume shows at 40 percent.
- **The pixel-to-ray rule gets one definition.** The march and the slice kernel both need it, so it moves
  into a `wp.func` in `render/raymarch.py`; the raw-frame digest test proves the march's bytes do not move.
- **The Sheet tab is drawn on the host**, as one image like the Volume view's: the background, then the
  current sheet cell composited over it with the contact sheets' own `composite` (so the card is exactly
  the contact sheet's look), resized bilinearly to the card's size on screen and pasted at its place. Only
  the visible part of the card is resized. One drawing path serves the screen, stills and clips.
- **The card's place.** In a recipe's Sheet tab the card's `seat` point sits on the seat emitter's center
  (`camera.seat`), its side is the sheet's `frame_m`, and it faces the camera; at Home it covers the
  volume's smoke. With `plume view OUT_DIR` there is no world: the card's center is the origin and the
  domain the navigation frames is a cube of `frame_m`.
- **One playhead.** The Sheet tab plays the same frame index as the Volume tab; the sheet's fps is the
  run's. Before a live run's sheet is assembled the Sheet tab says so.
- **The numbers strip's numbers come from the sheet**: `report/numbers.py`'s `measure` over the assembled
  frames (the same numbers `numbers.txt` holds), so they appear once the run's sheet is assembled. The
  marks: a frame whose smoke reaches an open face or the ceiling (measured as each frame lands, on the
  device, from the live grid: any cell in the layer beside that face at or above the density at which one
  cell shows one byte step) and a frame whose block of steps the CFL cap split (from the step log, at the
  end of the run). With `plume view OUT_DIR` the numbers are measured from the sheet's own frames, and the
  step-cap marks come from `settings.toml`'s `[resolved]` steps when it is beside the sheet.
- **A sheet folder's look** comes from its `settings.toml` (the resolved recipe `plume run` writes beside
  it); without one the schema's default look is used and a banner says so.
- **The transport moves into its own file** (`view/transport.py`), shared by the recipe window and the
  sheet-only window, and the numbers strip has its own (`view/numbers_strip.py`).
- **Clips and stills draw again at full resolution** for the current camera, view, tab, background, slice
  and A, B or Split (side by side); guides and text are not in them. A clip is an animated PNG with one
  image per kept frame (Volume) or per sheet frame (Sheet), each shown for `1 / fps`. Files go to
  `<out>/view/` (`--out`, else `out/<output.name>/`, else for a sheet folder the folder itself), named
  `<name>-f<frame>-<counter>.png` and `<name>-clip-<counter>.png`, the counter the next unused. The
  `.toml` beside each holds `[view]` (tab, view, background, side, frame or frames, fps, slice),
  `[camera]` (the navigation pose) and `[recipe]` (the resolved recipe, as `settings.toml` writes it, when
  there is one); `read_capture` reads it back and `Navigation.set_pose` restores the camera.

## Tasks

Built by the orchestrator in this thread, in order, one commit per task; the code-reviewer reviews the whole
slice at the end (run through a general-purpose agent, as in V1 and V2) and the verifier gates the final
commit on CPU.

### TV3.1 - Velocity in the frame cache, and edge marks (kernel)

- `view/frame_cache.py`: store center velocity (`vec3h`) beside smoke and temperature; the budget first
  drops velocity for the whole run, then thins frames; `has_velocity`, `load_velocity`; the thinning note
  says which.
- `view/live_run.py`: per landed frame, which open faces and whether the ceiling the smoke reached
  (`edge_kernel`, a gather over the six boundary layers, reduced in numpy).
- Tests: budget order (velocity first, then stride); a cached velocity equals the run's centered velocity
  rounded to 16 bits; the edge flags of a puff that rises into an open top.

### TV3.2 - The slice plane (kernel + window)

- `render/raymarch.py`: `pixel_ray` as a `wp.func`, used by the march.
- `view/slice_plane.py`: the plane's state (axis off/x/y/z, position, field), field preparation, the ramp
  table, `slice_kernel`, the legend's stops.
- `view/viewport.py`: `draw(..., plane=None)` overlays the slice.
- `view/app.py`: `L` cycles the axis, left drag moves the plane along its axis, the field's choice in the
  top bar, the legend.
- Tests: the kernel samples a known linear field exactly; a pixel whose ray misses the plane shows the
  dimmed volume; speed and swirl of a known rotation; the raw-frame digest stays.

### TV3.3 - The transport and the numbers strip (window)

- `view/transport.py` (playhead, play, speed, loop, stepping, the bar) out of `app.py`.
- `view/numbers_strip.py`: the series and marks (pure, tested) and the ImPlot strip with the playhead,
  which can be dragged.
- Tests: the series equal `measure` of the sheet; marks for edge frames and capped frames.

### TV3.4 - The Sheet tab (window)

- `view/sheet_player.py`: a `SheetSource` (frames, fps, frame_m, seat, look, channels) from a run's
  assembly or a sheet folder; the card's screen rectangle for a camera; `sheet_image` draws the tab.
- `view/app.py`: the Volume and Sheet tabs (`Tab`).
- Tests: at Home in orthographic the card's rectangle is the sheet's crop on screen; the card's pixels are
  the contact sheet's composite; a sheet folder loads (and one without `settings.toml` uses the default
  look); a folder without a sheet is refused.

### TV3.5 - `plume view OUT_DIR` (cli + window)

- `cli/view.py`: a folder opens the sheet-only window (no device, no simulation); `--out` for `plume
  view`.
- `view/sheet_app.py`: the sheet-only window: the card, navigation, transport, numbers strip, background.
- Tests: the command refuses a folder with no sheet (exit 2) and opens one with the extra installed (the
  window is not started in tests).

### TV3.6 - Clips and stills (window)

- `view/capture.py`: the output folder and names, `write_still`, `write_clip` (APNG), the `.toml`, and
  `read_capture`; `Navigation.set_pose`.
- `view/app.py`, `sheet_app.py`: `F12`, Save still and Save clip buttons, the notice of what was written.
- Tests: a clip has one image per kept frame with `1 / fps` durations; its `.toml` reloads to the same
  pose; names count up; a path-safe name.

### TV3.7 - Docs

- `README.md` and `CLAUDE.md`: `plume view OUT_DIR`, the new keys, where clips go and how a thread reads
  one; the backlog item's progress.
