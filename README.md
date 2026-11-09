# Plume

Plume simulates fire, smoke and explosions and renders them as flipbook sheets for realtime games. It is
built to be driven by an AI agent rather than a person at a GUI: a text recipe goes in; a sheet, its JSON,
contact sheets and a numbers file come out, in seconds.

Status: slice 1 of 6 (a buoyant smoke puff end to end). Combustion, turbulence, bursts and looping come in
later slices; see `docs/plans/2026-11-07-plume-slices.md`.

## Install and run

Needs [uv](https://docs.astral.sh/uv/). Python 3.13 and every dependency (NVIDIA Warp, numpy, Pillow) are
pinned in `uv.lock`.

```bash
uv sync
uv run plume run recipes/smoke_puff.toml --preview
uv run plume run recipes/smoke_puff.toml
```

On a machine with an NVIDIA GPU (Turing or newer, driver R580 or newer) kernels run on CUDA; elsewhere
they run on the CPU, which is fine for `--preview` and slow for full sheets.

`plume` exits with one of four codes, so a script or an agent can tell a bad recipe from a crash:

| Code | Meaning |
|------|---------|
| 0 | done |
| 1 | the run failed (no CUDA device, no frame shows any smoke, the sheet does not fit) |
| 2 | recipe error: a bad key, type or value, found by `plume check` before any simulation; a run that needs more than `solver.max_substeps` steps a frame also stops with 2 |
| 64 | usage error: an unknown flag or command, or a missing argument |

## The sheet

One RGBA PNG per flipbook, frames in rows, left to right and top to bottom. 8-bit linear:

| channel | meaning |
| --- | --- |
| R | heat (glow), normalized to the hottest frame of the sequence |
| G | thickness: smoke opacity, use as alpha |
| B, A | by layout, named in the JSON's `channels` (the recipe's `output.channels`): |
| | `heat,thickness,shade,unused` (the default): B is the shade, how lit the smoke is by the key light (`render.light_dir`) with its own shadow baked in, 1 for the brightest well-covered smoke of the run; A is 255 |
| | `heat,thickness,normal_x,normal_y`: B and A are the camera-space normal x and y of the smoke surface, -1..1 mapped to 0..255; +x right, +y up; rebuild z as `sqrt(1 - x^2 - y^2)` |

Every frame is cropped to the union of all frames' bounds (a square), with at least 2 empty pixels at
each edge. The JSON beside the sheet holds `frames`, `columns`, `frame_px`, `fps`, `frame_m` (frame width
in meters), `seat` (the emitter's point in the frame, as fractions from the top-left), `channels`,
`source`, `tool` and `written_by`.

The contact sheets composite each frame with the reference formula a game shader can match (linear
light, premultiplied):

```
color = background * (1 - G) + G * smoke_ramp(heat) * light + emission_ramp(heat)
```

with `light = 1 - shade_depth * (1 - shade)` in the shade layout and
`light = ambient + (1 - ambient) * max(0, normal . light_dir)` in the normal layout.

## The live viewer

`plume view` opens a window that runs a recipe on the GPU and shows the smoke in 3D while it simulates,
then loops the run so it can be judged in motion from any angle. It is an optional extra:

```bash
uv sync --extra view
uv run plume view recipes/smoke_puff.toml            # the full grid; --preview runs the preview grid
uv run plume view recipes/smoke_puff.toml --set forces.drag_per_s=0.4
```

The view is drawn by the sheet's own ray march with the contact sheets' look, so it shows what the sheet
will. Save the recipe (or a parent it `extends`) and the viewer re-runs it; a recipe error shows in a red
banner and the last good run keeps playing. The sheet itself still comes only from `plume run`.

**Tuning.** The right panel lists every recipe key by table: dimmed keys are defaults, plain keys are set by
the recipe, highlighted keys are changed in the viewer (each with a Reset). Click a number to type it (Enter
applies) or drag it, pick a choice or type text; the change applies when you let go, after the same checks as `plume
check` (a rejected value shows the message beside the field). What it does depends on the key's table, its
stage in `docs/recipe-reference.md`: a simulation key re-runs from time 0, a `[render]`, `[camera]` or
`[output]` key redraws from the kept frames, a `[look]` key only redraws. Ramps, colors and emitter names are
edited in the file. Drag the light arrow's tip (guides on) to move the key light. **Save** (Ctrl+S) writes
only the changed keys into the opened recipe and keeps its comments and layout; a key from an `extends`
parent is written into the opened recipe, never the parent. `--set` values start as unsaved edits, so Save
writes them in. Edits not yet saved stay applied when the file changes on disk, and a banner says how many.

**Compare.** Each change keeps the run before it as B. Nudging the same value again (several drags of one
slider) leaves B where it was, so B stays the look before the first nudge; changing another key moves B on.
**Hold B** keeps B where it is through every change until you turn it off. `C` (or Compare) flips the view to B at the same frame
and camera; Split shows A and B side by side; the panel lists the keys that differ.

| Input | Does |
|---|---|
| Alt + left drag | Tumble around the pivot |
| Alt + middle drag | Track (pan) |
| Alt + right drag, wheel | Dolly; in orthographic, change the view's size |
| Right mouse held | Free-look (cursor captured); releasing puts the pivot on the smoke under the center |
| Right mouse + W A S D, E Q | Fly forward, left, back, right, up, down (the first key switches to perspective) |
| Right mouse + wheel | Fly speed, x1.25 a notch |
| F, Shift+F | Frame the smoke of this frame; frame the whole domain |
| Home | The sheet camera (orthographic) |
| P | Orthographic or perspective |
| 1 2 3 4 | Look, Heat, Thickness, Shade (Normal in the normal layout) |
| G, B | Guides (domain box, 0.5 m floor ticks, emitters, light); cycle the background |
| Space, `,` `.`, Shift+`,` Shift+`.` | Play or pause; step a frame; first or last frame |
| Left drag on the light arrow's tip | Turn the key light (`render.light_dir`) |
| C | Compare: show B, the run before the last change |
| Ctrl+S | Save the panel's edits into the recipe |

`--cache-gb` (default 4) bounds the device memory the kept frames take; a run that does not fit keeps
every second (or fourth) frame and says so. The corner shows the redraw time and the run's time.

### Godot import settings

Import sheets as **Lossless** with **mipmaps on** and **Detect 3D off**. Godot's default 3D detection
switches a texture to VRAM Compressed, which damages the data channels.

## Docs

- `docs/recipe-reference.md`: every recipe key, generated from the schema.
- `docs/look-tuning.md`: what to change for what you see.
- `docs/specs/`: the design brief and spec. `CLAUDE.md`: how to work in this repo.
