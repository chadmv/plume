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

## The sheet

One RGBA PNG per flipbook, frames in rows, left to right and top to bottom. 8-bit linear:

| channel | meaning |
| --- | --- |
| R | heat (glow), normalized to the hottest frame of the sequence |
| G | thickness: smoke opacity, use as alpha |
| B, A | camera-space normal x and y of the smoke surface, -1..1 mapped to 0..255; +x right, +y up; rebuild z as `sqrt(1 - x^2 - y^2)` |

Every frame is cropped to the union of all frames' bounds (a square), with at least 2 empty pixels at
each edge. The JSON beside the sheet holds `frames`, `columns`, `frame_px`, `fps`, `frame_m` (frame width
in meters), `seat` (the emitter's point in the frame, as fractions from the top-left), `channels`,
`source`, `tool` and `written_by`.

The contact sheets composite each frame with the reference formula a game shader can match (linear
light, premultiplied):

```
color = background * (1 - G) + G * smoke_ramp(heat) * light(normal) + emission_ramp(heat)
```

### Godot import settings

Import sheets as **Lossless** with **mipmaps on** and **Detect 3D off**. Godot's default 3D detection
switches a texture to VRAM Compressed, which damages the data channels.

## Docs

- `docs/recipe-reference.md`: every recipe key, generated from the schema.
- `docs/look-tuning.md`: what to change for what you see.
- `docs/specs/`: the design brief and spec. `CLAUDE.md`: how to work in this repo.
