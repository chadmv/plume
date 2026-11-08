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
- **Smooth and blobby, no billows.** Add `forces.vorticity_confinement` (about 2 to 3 for a 0.3 m puff)
  to keep the curls the grid smears, and `forces.turbulence` with `scale_m` about half the puff's radius
  and a small `strength_mps2` (0.2 to 0.4) to break the surface up. Swirls bigger than the puff
  (`scale_m` near its size) shove the whole puff sideways instead of breaking it up.
- **Turbulence runs away or the CFL cap adds many steps.** Turbulence pushes all the air, not just the
  smoke, so without drag it keeps accelerating; the fastest swirl settles near a few times
  `strength_mps2 / drag_per_s` (the push peaks at about 3.4 times the strength). Give it some
  `forces.drag_per_s` (0.2 to 0.5). Drag also slows the buoyant rise, so a little goes a long way. The
  stdout `steps` line says how many steps the CFL cap added.
- **Strong confinement tears smoke into streaks.** Confinement feeds on the spin it creates; above about 4
  for a 0.3 m puff it shreds the smoke into thin strands.
- **Smoke never grows on its own.** Since slice 2 advection never adds smoke (before, clamped MacCormack
  added up to a third more over a puff's life, and doubled it with turbulence), so
  `dissipation.smoke_per_s` and open faces set how fast a puff fades. A small, sharp puff still loses a
  little to the scheme's blur.

## Iterating

- **Try a value without editing the recipe.** `plume run recipe.toml --preview --set forces.drag_per_s=0.4`
  changes one value for one run; `settings.toml` records the change under `[resolved] sets`. Name an
  emitter's keys by name (`emitter.puff.radius_m=0.4`) or index (`emitter[0].radius_m=0.4`).
- **Variations of one effect.** A recipe can start with `extends = "base.toml"` and give only what
  differs; tables merge key by key, and an `[[emitter]]` list replaces the parent's whole list.

## Density and color

- **Too solid or too faint.** `render.opacity_per_density` scales opacity for the same smoke amount;
  `emitter.smoke_per_s` adds more smoke.
- **The heat channel is black.** Gas only glows above `render.glow_start_k` (600 K by default); a warm puff
  below it has no heat, which is right for plain smoke.
- **Choosing smoke and fire colors.** Sample `look.smoke_ramp` and `look.emission_ramp` colors from the
  art reference for the effect you are making instead of guessing, and check both contact sheets before
  calling a look done. Tuning the smoke puff, a guessed light gray vanished on the neutral sheet and the
  next guess read pink on grass; sampling the game's reference image settled it.
- **Smoke barely shows on `contact_neutral.png`.** The default smoke color is a light warm gray close to
  the neutral background; judge on `contact_grass.png`, or change `look.smoke_ramp` (preview only).

## Shade (the default channel layout)

- **Which layout.** `output.channels = "heat,thickness,shade,unused"` (the default) bakes the key light and
  the smoke's own shadow into B, so a game multiplies its smoke color by it. `"heat,thickness,normal_x,normal_y"`
  writes the surface normal instead, for a game that lights the card itself. R and G are the same in
  both, so `numbers.txt`'s per-frame table does not change with the layout.
- **The light comes from the wrong side.** `render.light_dir` points toward the light in camera space
  (x right, y up, z toward the camera). It lights both layouts' contact sheets and bakes the shade.
- **Shadows too black or too flat.** `render.shade_fill` is the share of light that reaches every bit of
  smoke whatever shadows it (0.25 by default): raise it for softer, sky-lit shadows. `look.shade_depth`
  only changes the contact sheets (how dark a game would take a shade of 0); match it to the game's
  shader, not to taste.
- **Late frames go flat white in the shade column.** Thin smoke shadows itself little, and the shade is
  normalized over the whole run, so a fading puff ends fully lit. That is the light, not a bug.
- **A bright rim round the smoke.** Thin smoke at the silhouette, with a light leaning toward the camera
  (`light_dir` z above 0), is reached by light that passes beside the body, not through it. A light
  from behind or beside (z at or below 0) puts that rim in shadow.
- **Speckle or a dark outline at the smoke's edge.** Pixels thinner than `render.shade_fade_thickness`
  take the shade of their neighborhood (`render.shade_neighborhood_px`, in frame pixels), and empty pixels
  carry it too, so a game's filtering and mipmaps blend the edge into the body. Widen the neighborhood if
  thin wisps still speckle.
