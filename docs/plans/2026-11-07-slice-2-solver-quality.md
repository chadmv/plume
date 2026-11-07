# Slice 2 plan - solver quality and iteration tools

Date: 2026-11-07. Builds the slice 2 outline in `docs/plans/2026-11-07-plume-slices.md` and the backlog
item `docs/backlog/feature-2026-11-07-slice-2-solver-quality-iteration-tools.md`. Decisions: D7 (multigrid),
D9 (forces), D10 (CFL cap), D23 and D27 (`extends`, `--set`), D30 (preview is a coarse final).

## Corrections to inputs

- The spec's section 6.4 says `[resolved]` carries `substeps`; slice 1 writes `cells`, `size_m`, `fps`,
  `dt_s`, `warmup_steps` and `device` only. T2.5 adds the step counts.
- The preview step-length bug (`bug-2026-11-07-preview-step-size-differs-from-final`) is fixed in its own
  thread. This slice does not change `recipe/derived.py`'s base step or the emitter blend; the CFL cap
  (T2.5) works on whatever base step the recipe resolves to, block by block.

## New recipe keys

All go in `recipe/schema.py`; `docs/recipe-reference.md` is regenerated in the same commit.

| Key | Default | Meaning |
|-----|---------|---------|
| `extends` | `""` | Parent recipe, relative to this file; deep-merged under this one (T2.1) |
| `solver.pressure_solver` | `"multigrid"` | `multigrid` or `gauss_seidel` (T2.2) |
| `solver.pressure_iterations` | 60 | Gauss-Seidel sweeps (unchanged; used by `gauss_seidel` only) |
| `solver.multigrid_cycles` | 2 | V-cycles per solve (T2.2, measured) |
| `solver.multigrid_sweeps` | 2 | Smoothing sweeps before and after each level's correction (T2.2) |
| `solver.max_cells_per_step` | 1.0 | CFL cap: the fastest gas may cross at most this many cells per step (T2.5) |
| `solver.max_substeps` | 32 | Ceiling on steps per frame from the cap; past it a run fails with a recipe error naming the key (T2.5) |
| `forces.wind_mps` | `[0, 0, 0]` | The surrounding air's velocity; drag pulls the gas toward it (T2.3) |
| `forces.drag_per_s` | 0 | Rate the gas's velocity relaxes toward `wind_mps` (T2.3) |
| `forces.vorticity_confinement` | 0 | Fedkiw confinement strength, 1/s; the push is `strength * cell_m * (N x curl)` (T2.3) |
| `turbulence.scale_m` | 0.3 | Size of the swirls (T2.4) |
| `turbulence.strength_mps2` | 0 | Acceleration of the swirling push; 0 turns it off (T2.4) |
| `turbulence.speed_mps` | 0.2 | How fast the pattern changes: it renews every `scale_m / speed_mps` seconds (T2.4) |

## Tasks

Order: T2.1 is independent of the solver tasks; T2.2 to T2.5 share `sim/stepper.py` and the schema and
run in sequence. Nothing runs in parallel, since every task touches `recipe/schema.py`.

### T2.1 - `extends` and `--set` (pipeline)

- `recipe/variation.py`: `resolve_extends(table, path)` reads the parent (relative to the child's folder),
  resolves the parent's own `extends` first, and deep-merges: tables merge key by key, anything else
  (numbers, text, lists, the `[[emitter]]` list) replaces the parent's value. Chains are allowed; a cycle
  or a depth past 8 fails. The path must be relative (no drive letter, no leading `/` or `\`) and end in
  `.toml`, since a machine-local path breaks the standalone rule.
- `apply_sets(table, ["key=value", ...])`: dotted keys (`forces.drag_per_s=0.5`), emitters by name
  (`emitter.puff.radius_m=0.4`) or index (`emitter[0].radius_m=0.4`). The value is read as a TOML value;
  if that fails it is taken as text (`domain.faces.top=closed`). Unknown keys are caught by the existing
  build step with its "did you mean" hint. A malformed `--set` (no `=`, an unknown emitter) is a recipe
  error, exit 2.
- Order: file, `extends` merge, `--set`, build and rules, `--preview`, dependent defaults.
- `settings.toml` stays rerunnable: the resolved recipe has `extends = ""`, and `[resolved]` records
  `extends_chain` (paths as written) and `sets` (the `--set` strings).
- CLI: `--set` (repeatable) on `run` and `check`.
- Tests: child overrides one key and inherits the rest; nested table merge; `[[emitter]]` replaces; a
  grandparent chain; a cycle fails; an absolute path fails; a missing parent fails naming the path;
  `--set` on a number, a vector, an emitter by name and by index, a bare text value; an unknown `--set`
  key fails with the hint; `settings.toml` of an extended recipe loads back to the same recipe.

### T2.2 - Geometric multigrid pressure (kernel)

- `sim/multigrid.py`: a hierarchy of levels, each with its own `GridInfo` (dims `ceil(n / 2)` of the level
  above, cell size doubled, the same open faces), down to a level with a dimension of 2 or less (or 8
  levels). Kernels, all gathers: residual `r = b - L q`; restriction by averaging the children that exist;
  trilinear prolongation of the coarse correction (clamped at the edges) added to the fine solution;
  red-black Gauss-Seidel smoothing with relaxation 1. The coarsest level gets a fixed 20 sweeps.
- `pressure.project(grid, solver)`: dispatches to Gauss-Seidel or multigrid; the hierarchy is allocated
  once per grid. Warm start from the previous step's pressure is kept.
- Measure first: on 16 cubed with the slice 1 random-velocity test, and on the preview grid of the smoke
  puff (38 x 48 x 38), the divergence left after 1, 2 and 3 V-cycles against 60 Gauss-Seidel sweeps, and
  the time. Defaults are set from that measurement and the measurement is written in the test.
- Tests: multigrid with the default cycles leaves less divergence than 60 Gauss-Seidel sweeps on the
  closed and open 16-cubed cases; odd dimensions (15 x 17 x 13) converge too; closed walls stay exactly
  zero; the Gauss-Seidel path still passes its slice 1 tests.

### T2.3 - Wind, drag and vorticity confinement (kernel)

- `sim/forces.py`: `apply_drag` relaxes each face velocity toward `wind_mps` by `1 - exp(-drag_per_s *
  dt)`. A recipe with wind and no drag is an error (wind would do nothing).
- `sim/vorticity.py`: curl at cell centers from the face velocities, then a face kernel computes `N =
  grad|curl| / |grad|curl||` from the neighbors' magnitudes and adds `strength * cell_m * (N x curl) * dt`
  averaged to the face. Two passes, both gathers, a scratch vector field for the curl.
- Stepper order (spec 3.2 step 2): buoyancy, vorticity confinement, turbulence (T2.4), drag.
- Tests: drag with no wind brings a uniform velocity to `exp(-drag * t)` of itself within 1 percent;
  drag with wind approaches the wind; confinement off changes nothing (bit for bit); confinement on a
  single vortex tube raises its peak curl after 10 steps against confinement off; the push scales with
  `cell_m` (same field at two cell sizes).

### T2.4 - Curl-noise turbulence (kernel)

- `sim/turbulence.py`: a vector potential of three value-noise components in `sim/noise.py`'s hash
  (streams far above emitter indices), sampled at `position / scale_m` and blended in time between
  lattice slices `t * speed_mps / scale_m` with the same smooth fade. The push on each face is the
  discrete curl of that potential taken at the face's edges, so its discrete divergence is zero and the
  projection leaves it alone. Acceleration is `strength_mps2` times the curl in lattice units.
- Tests: strength 0 changes nothing; the discrete divergence of the push alone is below 1e-4 of its
  magnitude; same seed gives identical bytes, another seed differs; the pattern at time 0 and at
  `scale_m / speed_mps` differ, at nearby times are close; the push at a preview cell size and a final
  cell size agree within 10 percent at matching points (it is in meters, D30).

### T2.5 - The CFL substep cap (kernel and pipeline)

- `sim/run.py`: time runs in blocks, one per frame (warmup in blocks of the same base step count, the last
  one shorter). Before each block, the largest speed is the larger of the grid's fastest face velocity
  (copied to the host, numpy float64) and the fastest emitter active in the block. Steps in the block are
  `max(base, ceil(speed * block_s / (max_cells_per_step * cell_m)))`; past `max_substeps` the run stops
  with a recipe error. Step times are `block_start + i * block_s / n`, so the clock never drifts.
- The per-frame counts are returned and written to `[resolved]` as `steps_per_frame` (a list) and
  `total_steps`; the stdout summary prints the total and how many the cap added.
- Tests: a slow puff keeps its base count in every frame (the cap changes nothing; bit for bit against
  the uncapped loop); an emitter at 10 m/s in a 0.1 m grid forces more steps, as computed; past
  `max_substeps` is an error; two runs give the same counts.

### T2.6 - Advection smoke loss: measure and decide (kernel)

- Measure, in a closed box at preview and final cell sizes for the puff, total smoke lost by clamped
  MacCormack over the effect, with and without turbulence. If preview and final lose amounts that differ
  enough to change the look (more than 3 percent of total smoke apart), add a conservative correction;
  otherwise close the backlog item with the numbers and leave the scheme as it is.

### T2.7 - The turbulent puff, look review and golden (look-tuner, orchestrator)

- Tune `recipes/smoke_puff.toml` with turbulence and vorticity until it billows instead of rolling into a
  dome; compare preview and final contact sheets; send the user both. After approval, regenerate
  `tests/golden/smoke_puff_preview.numbers.txt` from a fresh run of the committed recipe.
- `docs/look-tuning.md`: entries for turbulence, vorticity, drag and wind.

### T2.8 - Close

- Whole-slice review, security review, verifier gate, pull request, retro, backlog updates.
