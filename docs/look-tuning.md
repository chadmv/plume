# Look tuning

What you see on the contact sheets or in `numbers.txt`, and which recipe values to change. Add an entry
whenever a run teaches something.

## Framing

- **The effect is small in its frames.** The crop is the union of every frame's bounds, so anything that
  travels (a rising puff) makes every frame cover the whole trip. Reduce the travel: lower
  `emitter.temperature_k` (less lift), lower `emitter.velocity_mps`, or shorten `time.duration_s`.
  `numbers.txt` shows the travel in the `top` and `bottom` columns.
- **A faint fringe widens the crop.** Any pixel whose thickness byte is at least 1 counts as content.
  Thin trailing smoke (the wake under a rising puff) can set the bounds; fading it faster
  (`dissipation.smoke_per_s`) tightens them.

## Timing

- **`fade_frame` is `never`.** The smoke is still above 10 percent of its peak thickness at the last frame.
  Raise `dissipation.smoke_per_s` or lengthen `time.duration_s`. The puff in `recipes/smoke_puff.toml`
  fades by frame 61 with 1.6 per second over 2.4 s.

## Shape

- **A hot puff becomes a flat dome or a jellyfish.** Buoyant puffs roll up into a vortex ring. Less heat
  above ambient and a slower launch keep it rounder. Turbulence and vorticity confinement (slice 2) add
  billows.
- **A puff loses some smoke even with no dissipation.** Semi-Lagrangian advection is not conservative:
  a small, sharp puff loses about 10 percent over 40 steps. Larger, softer puffs lose less.

## Density and color

- **Too solid or too faint.** `render.opacity_per_density` scales opacity for the same smoke amount;
  `emitter.smoke_per_s` adds more smoke.
- **The heat channel is black.** Gas only glows above `render.glow_start_k` (600 K by default); a warm puff
  below it has no heat, which is right for plain smoke.
- **Choosing smoke and fire colors.** Sample `look.smoke_ramp` and `look.emission_ramp` colors from the
  art reference (`docs/art-direction/reference/fireball-impact-meadow.png` in the `chadmv/petri`
  repository) instead of guessing,
  and check both contact sheets before calling a look done: a guessed light gray vanished on the neutral
  sheet and the next guess read pink on grass.
- **Smoke barely shows on `contact_neutral.png`.** The default smoke color is a light warm gray close to
  the neutral background; judge on `contact_grass.png`, or change `look.smoke_ramp` (preview only).
