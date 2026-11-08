---
date: 2026-11-08
topic: shade-channel-layout
branch: claude/project-thread-kexx2n
range: 63275fe..HEAD
---

# Session Retro: 2026-11-08 - Shade channel layout

**TL;DR:** Plume's sheets can now carry a baked, self-shadowed shade instead of a surface normal in their
blue channel, and that is the new default: the smoke is lit by one key light with its own shadow baked
in, so a game gets a dense, rounded look from a single multiply, and alpha is simply 255. A recipe can
still ask for the old normal layout, which writes exactly what it did before. Heat and thickness are
unchanged in both, so the smoke puff's per-frame numbers match the approved look; its new shaded look
waits on Chad's review, and the GPU tests wait on a PC run.

## Handoff

- Built from `docs/backlog/feature-2026-11-07-shade-channel-layout.md` and its design
  `docs/specs/2026-11-07-shade-channel-design.md` (amendment A4). Plan: `docs/plans/2026-11-07-shade-channel-layout.md`
  (T1 to T6; its "Corrections to inputs" records the two deviations below).
- New keys: `output.channels` (default `heat,thickness,shade,unused`, or `heat,thickness,normal_x,normal_y`),
  `render.light_dir` (was `look.sun_dir`; the old key fails with "it moved to render.light_dir" via
  `schema.MOVED_KEYS`), `render.shade_fill`, `render.shade_fade_thickness`, `render.shade_neighborhood_px`,
  `look.shade_depth`. Layout strings are defined once in `recipe/schema.py` (`SHADE_LAYOUT`, `NORMAL_LAYOUT`).
- Code: `render/light_volume.py` (gather kernel, one thread per cell), `raymarch.py` shade branch,
  `sheet/shade.py` (easing, `shade_divisor`), layout-aware `resample`, `soften`, `quantize`, `composite`,
  `channels`, `numbers` (summary gains `channels` and `shade_divisor`).
- Tests: 144 pass, 2 skip (GPU) on cloud CPU. The same-bytes CLI test runs in both layouts; the GPU
  same-bytes test uses the default layout, so it covers the light volume kernel, and needs a PC run.
- Smoke puff in the new default, cloud CPU: preview 47.8 s (simulate 44.2, render 3.1); full 578 s
  (simulate 414, render 161), peak frame 5, fade frame 58, `frame_m` 1.3905, the same as the approved
  slice 2 look. The preview's per-frame table is identical to `tests/golden/smoke_puff_preview.numbers.txt`;
  only the summary gains two lines, refreshed once Chad approves the look.
- The backlog item stays open until Chad approves the shaded puff and the golden summary is refreshed.
- Next: Chad's look review of the shaded puff, then the PC run (`uv run pytest` with the gpu tests, GPU
  preview and full timing), then slice 3.

## What Was Built

- A light volume: each frame, every cell's share of the key light through the smoke toward the light.
- The camera march averages that light (lifted by a fill share) over the smoke it sees, giving the shade.
- Sheet assembly eases thin and empty pixels to the shade of the body they belong to, so filtering and
  mipmaps blend an edge into the smoke instead of speckling or outlining it, then maps the brightest
  well-covered smoke of the run to 255.
- Contact sheets, the channel strip and `numbers.txt` follow the layout; the README describes both.

## Key Decisions

- **Shade kept times thickness in the raw frame.** The design resampled and softened plain shade, which
  mixed an edge pixel's shade with the empty pixels' 0 and drew the dark outline the easing exists to
  prevent (a test ball's darkest edge byte fell from 85 to 7). Weighted by thickness, every filter treats
  shade as it treats thickness; the easing step divides it back out.
- **A smooth lean toward the frame's mean** replaces the design's "where the blurred thickness is zero":
  bicubic ringing leaves faint pixels with thickness but no shade, and a hard zero test let their
  neighborhoods read 0.
- **The renderer runs only its layout's volume pass** (light volume or normal field) and hands the kernel
  a one-cell stand-in for the other.

## What Went Wrong and What Changes

Ledger of slice 2's lessons: "measure the example recipe at preview and final sizes" was applied (the
full smoke puff ran before the look review); "a correction that rescales a field gets a leaving-the-domain
test" was not exercised; "run forces-heavy looks at full size once" was applied; "merge main after the
first push" was not exercised; the engineer split recurred (the orchestrator built the tasks itself and
ran the code-reviewer as a general-purpose agent loading `.claude/agents/code-reviewer.md`, which again
found a real bug).

- **A guard that never ran passed the whole suite.** The shade clip after resampling compared a list to
  the layout string, because a local variable reused the parameter's name; 144 tests passed and the
  reviewer found it with a probe (up to 70 levels of B changed). -> **What changes:** when code adds a
  guard against a numerical artifact (a clip, a clamp, a fallback), its commit carries a test that fails
  with the guard removed, checked by removing it once.
- **A "measured" test comment was written before the measurement.** The first draft of the shadow test
  quoted numbers from expectation; the probe then gave different ones. -> **What changes:** a test's
  "Measured:" comment is pasted from the probe's output, never written ahead of it.
- **An opacity-weighted value filtered without its weight drew an outline.** Caught by probing the
  halo test's bytes before setting its bound. -> **What changes:** when a channel is an average weighted
  by opacity, carry it multiplied by thickness through every linear filter and divide at the end.
- **The stale full run.** The background full run had started before the clip fix, and Python had already
  imported the old module, so its outputs were wrong though the files on disk were fixed. -> **What
  changes:** after fixing code, restart any run that began before the fix.

## Recommended Backlog Items

- See [Cut the light volume's cost on CPU full runs](../backlog/idea-2026-11-08-light-volume-cpu-cost.md) -
  160 s of a 578 s cloud CPU full run is rendering; GPU cost unmeasured.

## Files Most Touched

- `src/plume/render/light_volume.py`, `src/plume/render/raymarch.py`, `src/plume/render/frame_renderer.py`
- `src/plume/sheet/shade.py`, `src/plume/sheet/assemble.py`, `src/plume/sheet/resample.py`, `src/plume/sheet/quantize.py`
- `src/plume/report/composite.py`, `src/plume/report/channels.py`, `src/plume/recipe/schema.py`
- `README.md`, `docs/look-tuning.md`
