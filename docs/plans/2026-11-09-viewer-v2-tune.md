# Live viewer slice V2 Tune plan

Date: 2026-11-09. Builds slice V2 of `docs/specs/2026-11-08-live-viewer-design.md` (section 10, item 2),
tracked by `docs/backlog/feature-2026-11-07-live-interactive-simulation-viewer.md`. The design is settled
(V11 to V14 and V12, merged in PR #12) and V1 Watch merged as PR #13, so this goes straight from intake to
plan.

Done when a value dragged in the viewer and saved gives the same look through `plume run`.

## Scope

In V2: a stage on every recipe table (V11) and in the recipe reference; the editing panel (V13); Save with
tomlkit and reload with unsaved edits kept (V14); `--set` values as edits; Compare and Split (V12) with the
list of keys that differ; the light arrow drag (section 4.2).

Left to V3 as section 10 says: the Sheet tab and `plume view OUT_DIR`, the numbers strip, the slice plane,
clips and stills.

## Corrections to inputs

- **Four kinds of work, not three.** V11 names what each stage does. Two stages need the sheet camera's raw
  frames again, which a redraw does not give: the raw frames hold the render settings (opacity, glow, the
  light) and the sheet camera, and the viewer's heat and shade divisors and Home's crop come from them. So:
  - a **simulation** change re-runs from time 0, as V11 says;
  - a **render** or **sheet** change *re-captures*: a new run object that shares the old run's frame cache,
    renders each kept frame's sheet-camera raw frame again with the new settings (one frame per window
    update, like a live run), then assembles for new divisors and crop. Playback carries on meanwhile with
    the old divisors. The redraw itself is immediate. A re-capture reads the 16-bit kept fields, so its
    divisors can differ from `plume run`'s in the last digits; the sheet stays `plume run`'s. When the cache
    was thinned (not every frame kept) or the run is still simulating, a render or sheet change re-runs
    instead, which is always correct;
  - a **look** change only redraws (a new viewport over the same run);
  - **`[preview]`** has its own stage: its values reach the run only through the tables they override under
    the Preview toggle (`domain.cell_m`, `time.frames`, `time.substeps`, `output.frame_px`), so the change
    is judged by those tables. With Preview off a `[preview]` edit changes nothing on screen.
  What changed is read off the two resolved recipes, table by table, and the strongest stage wins.
- **Edits apply when a field is let go, for every stage.** V11 asks this of simulation values; render and
  look values also wait for the release (or Enter), so one drag is one change, and one entry for Compare.
  The light arrow follows the mouse while it is dragged and is applied on release.
- **What B is.** Every applied change (a re-run, a re-capture or a redraw) makes the current A into B, except
  while A is still simulating: a change during a live run replaces A and keeps B, so B is always a run that
  got somewhere. A change that alters nothing on screen (a comment, a `[preview]` key with Preview off, a
  Save the file already holds) keeps B.
- **Cache budget with B.** B's frames stay on the device. A re-run's cache gets `--cache-gb` less what B's
  own cache holds (nothing when they share one), and the thinning note says when B took the room.
- **Each viewport owns its widening scratch.** In V1 the frame cache widened into one pair of scratch
  arrays per cache, used by the one viewport. With A and B (and a re-capture) reading the same cache, each
  reader passes its own pair.
- **The panel shows the recipe as the file means it.** Values are the recipe parsed with the viewer's edits
  but before `--preview` is applied and before dependent defaults are filled, so `temperature_k = -1` reads
  as -1 (its tooltip says it means ambient) and an edit under Preview changes the full-grid value it names.
  "Set by the recipe" means the key is in the merged file and its parents.
- **Floats are rounded to six significant digits** when an edit is applied (ImGui's drag fields are float32,
  so a dragged 0.35 would otherwise save as 0.3499999940395355).
- **A key from a parent's `[[emitter]]`.** Lists replace whole in `extends` merging, so writing one emitter
  key into a child that has no `[[emitter]]` of its own copies the parent's emitter list into the child
  first; Save reports that it did.
- **Read-only in the panel:** `extends`, emitter names (they are the emitters' identities), the ramps and
  background colors (V13), as V13 says.
- **Emitter names must be plain** (added after review): key paths name emitters as `emitter.<name>.<key>`,
  so `recipe/rules.py` rejects a name holding `.`, `[` or `]` (or an empty one).
- **The panel lives in `view/panel.py`**, not `app.py` (section 6 lists no file for it), to keep the window
  file to its job.
- **tomlkit** (0.15.2, as section 7 says) joins the `view` extra in this slice, pinned in `uv.lock`.

## Tasks

Built by the orchestrator in this thread, in order, one commit per task; the code-reviewer reviews the whole
slice at the end (run through a general-purpose agent, as in V1) and the verifier gates the final commit.

### TV2.1 - Stages in the schema (pipeline)

- `recipe/schema.py`: stage names `simulation`, `render`, `look`, `sheet`, `preview` with one line each
  saying what a change does; `section(doc, stage)` and `setting(..., stage=...)` for top-level keys;
  `stage_of(key_path)` (a nested key inherits its top-level table's stage).
- `recipe/reference.py`: each table's heading says its stage; regenerate `docs/recipe-reference.md`.
- Tests (`tests/recipe/test_stages.py`): every top-level field has a stage; `stage_of` for a nested key, an
  emitter key and `seed`; the reference names each table's stage.

### TV2.2 - Recipe keys and edits (pipeline)

- `recipe/variation.py`: `apply_values(table, values)` applies `(key, value)` pairs with `--set`'s key
  rules (`apply_sets` becomes parse then apply); `set_items(sets)` parses `--set` items into pairs.
- `view/recipe_keys.py`: `flat_values(recipe)` (every leaf key path, emitters by name), `key_info(path)`
  (type, unit, doc, choices, stage, read-only), `changed_keys(a, b)` and `strongest_stage`.
- Tests: every schema leaf appears; an emitter key path round-trips through `apply_values`; the stage of a
  change set.

### TV2.3 - Recipe writer (pipeline)

- `view/recipe_writer.py`: `write_edits(path, edits, merged)` writes only the edited keys with tomlkit,
  keeping comments, blank lines, order and line endings; tables and inline tables it needs are created; an
  emitter is found by `name`; a parent's emitter list is copied in first when the child has none. Writes
  through a temporary file and a replace.
- Tests (section 9's list): comments, blank lines and order survive; a key from a parent lands in the child;
  an emitter's inline `noise` key; the copied emitter list; the saved recipe loads to the edited values;
  no edits changes no byte; CRLF stays CRLF; `recipes/smoke_puff.toml` as it is.

### TV2.4 - Re-capture and per-reader scratch (kernel)

- `frame_cache.py`: `load(frame, into)` widens into the caller's pair; `scratch()` makes a pair;
  `stored_bytes`. `frame_renderer.py`: `render_fields(smoke, temperature, info)`, which `render(grid)` calls
  (no byte change). `live_run.py`: `LiveRun.recapture(source, recipe)`; divisors fall back to the source's
  until its assembly lands; `simulation_id` shared with the source.
- Tests: a re-capture with unchanged settings gives raw frames within float16 rounding of the live run's;
  one with a doubled `opacity_per_density` gives thicker frames; the old run's frames are untouched.

### TV2.5 - Session: edits, stages, A and B, Save (pipeline)

- `view/session.py`: `Snapshot(recipe, run, viewport)` for A and B; `edit`, `reset`, `revert`, `save`;
  reload applies unsaved edits over the file and notes how many; `--set` items start as edits; the work kind
  chosen by stage (TV2.1, corrections above); the budget beside B.
- Tests: a render edit re-captures and never re-runs; a look edit redraws only; a simulation edit re-runs;
  `[preview]` with Preview off does nothing; a rejected edit is not applied and returns `plume check`'s
  message; B is the run before; a change during a live run keeps B; unsaved edits survive a reload with
  the note; Save writes, clears the edits, and the reload starts no run.

### TV2.6 - Light arrow drag (view)

- `view/guides.py`: `turn_light(world_dir, dx_px, dy_px, camera)` (yaw about world up, pitch about the
  view's right) and `light_dir_in_camera(world_dir, camera)` (inverse of `toward_light_world`).
- Tests: no motion keeps the direction; the inverse round-trips; a sideways drag keeps the vertical part.

### TV2.7 - The window (view)

- `view/app.py`: the right panel (V13: tables as collapsing headers with their stage, drag fields, vector
  fields, drop-downs, text, Reset per key, Revert, Save and Ctrl+S, field errors, the unsaved count); `C`
  and the Compare button, Split, the A/B differences; the light arrow drag (left drag near its tip); the
  banner for edits kept over a reload; the progress bar names a re-capture.
- Check: a scripted smoke run under `xvfb-run` in the cloud (edit, save, compare, split); the real check is
  on the PC.

### TV2.8 - Docs (orchestrator)

- `README.md` (the panel, Save, Compare, Split, the arrow), `CLAUDE.md` (the loop: tune in the viewer, Save,
  then `plume run`), the backlog item's progress.

### TV2.9 - On the PC (verifier, by hand)

- `uv sync --extra view`, `uv run pytest` (gpu tests included).
- `uv run plume view recipes/smoke_puff.toml`: drag a render value and a simulation value, Compare, Split,
  drag the light arrow, Save; then `plume run --preview` of the saved recipe shows the same look. The user's
  look at it on the PC ends the slice.
