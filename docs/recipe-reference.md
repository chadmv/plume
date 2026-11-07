# Recipe reference

Generated from `src/plume/recipe/schema.py` by `uv run python -m plume.recipe.reference`; do not edit by
hand. Every key carries its unit in its name. Unknown keys are errors. `[look]` only changes the contact
sheets, never the sheet.

## Top level

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `extends` | - | `""` | Parent recipe this one builds on, as a path relative to this file. Tables merge key by key; any other value, `[[emitter]]` included, replaces the parent's. Empty in a resolved recipe. |
| `seed` | - | `0` | Seed for every random choice in the run. |

## [domain]

The simulation box.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `size_m` | m | required | Width, height and depth of the simulation box. Its origin is the center of the floor. |
| `cell_m` | m | required | Edge length of one grid cell. |
| `ambient_k` | K | `293.0` | Temperature of the surrounding air. |

## [domain.faces]

Each face of the box is `closed` (a solid wall) or `open` (material leaves freely).

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `bottom` | - | `"closed"` | Floor of the domain (y minimum). One of: `closed`, `open`. |
| `top` | - | `"open"` | Ceiling of the domain (y maximum). One of: `closed`, `open`. |
| `left` | - | `"open"` | x minimum face. One of: `closed`, `open`. |
| `right` | - | `"open"` | x maximum face. One of: `closed`, `open`. |
| `back` | - | `"open"` | z minimum face, away from the default camera. One of: `closed`, `open`. |
| `front` | - | `"open"` | z maximum face, toward the default camera. One of: `closed`, `open`. |

## [time]

Effect time and frames.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `duration_s` | s | required | Effect time covered by the flipbook. |
| `frames` | - | `64` | Number of flipbook frames, evenly spaced over the duration. |
| `substeps` | - | `3` | Simulation steps per frame. |
| `warmup_s` | s | `0.0` | Simulated time before frame 0. |

## [[emitter]]

Sources of smoke, heat and motion.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `name` | - | required | Name, used by `camera.seat`. |
| `shape` | - | `"sphere"` | Emitter shape. One of: `sphere`, `box`. |
| `center_m` | m | required | Center of the shape. |
| `radius_m` | m | `0.0` | Radius of a sphere. |
| `size_m` | m | `[0.0, 0.0, 0.0]` | Width, height and depth of a box. |
| `edge_softness` | - | `0.3` | Outer fraction of the shape over which emission fades to 0. |
| `start_s` | s | `0.0` | Effect time the emitter starts. |
| `end_s` | s | required | Effect time the emitter stops. |
| `smoke_per_s` | 1/s | `0.0` | Smoke density added per second at full coverage. |
| `temperature_k` | K | `-1.0` | Temperature the emitter holds its cells at; -1 means ambient. |
| `velocity_mps` | m/s | `[0.0, 0.0, 0.0]` | Velocity the emitter holds its cells at. |
| `velocity_mode` | - | `"fixed"` | `fixed` uses `velocity_mps`; `outward` pushes away from the center at the length of `velocity_mps`. One of: `fixed`, `outward`. |

## [emitter.noise]

Seeded breakup of the emitter's shape.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `scale_m` | m | `0.1` | Size of the emitter's breakup pattern. |
| `strength` | - | `0.0` | How strongly the pattern breaks up the emitter; 0 for none. |

## [forces]

Forces on the gas.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `gravity_mps2` | m/s^2 | `9.81` | Strength of gravity. |
| `heat_buoyancy` | - | `1.0` | Lift from heat; 1 is ideal-gas buoyancy. |
| `smoke_weight` | - | `0.0` | Sink from smoke density, as a fraction of gravity per unit density. |
| `wind_mps` | m/s | `[0.0, 0.0, 0.0]` | Velocity of the surrounding air; drag pulls the gas toward it, so it needs `drag_per_s`. |
| `drag_per_s` | 1/s | `0.0` | Rate the gas's velocity relaxes toward `wind_mps`; 0 for none. |
| `vorticity_confinement` | 1/s | `0.0` | Strength of the push that keeps small swirls alive (Fedkiw 2001), scaled by the cell size so previews keep their swirl; 0 for none. |

## [forces.turbulence]

Seeded curl-noise swirls, in meters, so previews match.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `scale_m` | m | `0.3` | Size of the swirls. |
| `strength_mps2` | m/s^2 | `0.0` | Acceleration of the swirling push; 0 for none. |
| `speed_mps` | m/s | `0.2` | How fast the swirl pattern changes: it renews every `scale_m / speed_mps` seconds; 0 freezes it. |

## [dissipation]

How smoke and heat fade.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `smoke_per_s` | 1/s | `0.0` | Rate smoke fades. |
| `cooling_per_s` | 1/s | `0.0` | Rate temperature relaxes toward ambient. |

## [solver]

Solver controls.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `pressure_solver` | - | `"multigrid"` | How the pressure is solved: `multigrid` (fixed V-cycles) or `gauss_seidel` (slice 1's fixed sweeps). One of: `multigrid`, `gauss_seidel`. |
| `pressure_iterations` | - | `60` | Red-black Gauss-Seidel sweeps per pressure solve, for `gauss_seidel`. |
| `multigrid_cycles` | - | `2` | Multigrid V-cycles per pressure solve. |
| `multigrid_sweeps` | - | `2` | Smoothing sweeps before and after each multigrid level's correction. |
| `max_cells_per_step` | cells | `1.0` | CFL cap: the fastest gas, measured at the start of each frame, may cross at most this many cells in one step; frames that would go further get more, shorter steps. |
| `max_substeps` | - | `32` | Most steps the CFL cap may give one frame; a frame that needs more stops the run with an error. |

## [camera]

The orthographic camera.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `elevation_deg` | deg | `0.0` | How far the camera looks down; 0 is a level side view. |
| `azimuth_deg` | deg | `0.0` | Orbit around the vertical axis, counterclockwise seen from above; 0 looks along -z. |
| `seat` | - | `""` | Emitter whose center is the seat point; empty means the first emitter. |

## [render]

Turning the volume into sheet channels.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `px_per_cell` | - | `2.0` | Pixels per cell when rendering the whole domain view. |
| `opacity_per_density` | 1/m | `4.0` | Opacity per unit smoke density per meter of ray. |
| `glow_start_k` | K | `600.0` | Temperature where heat starts to glow. |
| `smoke_hides_heat` | - | `1.0` | How much smoke in front hides glow behind it, 0 to 1. |
| `normal_blur_cells` | cells | `1.5` | Blur applied to smoke before taking surface normals. |
| `normal_fade_thickness` | - | `0.1` | Below this thickness, normals fade to face the camera. |
| `soften_px` | px | `0.75` | Gaussian blur on the final frames. |
| `crop_margin` | - | `0.04` | Empty margin around the content, as a fraction of the frame. |

## [output]

The sheet's size and name.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `name` | - | `""` | Output name; empty means the recipe file's name. |
| `frame_px` | px | `256` | Width and height of one frame. |
| `columns` | - | `0` | Frames per sheet row; 0 means the smallest square grid. |

## [preview]

Overrides used by --preview.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `longest_axis_cells` | cells | `48` | Cells along the domain's longest axis in --preview. |
| `frames` | - | `16` | Frames in --preview; substeps rise so each step is as long as a full run's. |
| `frame_px` | px | `128` | Frame size in --preview. |

## [look]

Contact sheet colors; never affects the sheet.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `ambient` | - | `0.65` | Light every smoke surface gets, 0 to 1. |
| `sun_dir` | - | `[-0.5, 0.7, 0.5]` | Direction toward the sun in camera space (x right, y up, z toward the camera). |
| `smoke_ramp` | - | `[[0.0, "#aea193"], [0.4, "#bc9c84"], [0.75, "#dca07a"], [1.0, "#f5b47e"]]` | Smoke color by heat, as [position, sRGB] stops (cool end from the reference's sunlit smoke). |
| `emission_ramp` | - | `[[0.0, "#000000"], [0.2, "#3a0c04"], [0.5, "#c4441a"], [0.8, "#ff9a3a"], [1.0, "#fff2c2"]]` | Glow color added by heat, as [position, sRGB] stops. |
| `contact_px` | px | `128` | Thumbnail size on the contact sheets. |

## [look.backgrounds]

Contact sheet backgrounds.

| key | unit | default | meaning |
| --- | --- | --- | --- |
| `neutral` | sRGB | `"#808080"` | Background of contact_neutral.png. |
| `grass` | sRGB | `"#aac476"` | Background of contact_grass.png (Petri's mid grass). |
