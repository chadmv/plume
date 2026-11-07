# Plume

A fire, smoke and explosion simulator that renders flipbook sheets for realtime games, built for an agent
to drive: write a TOML recipe, run it, read the contact sheets and numbers, change a value, run again. The
first consumer is Petri (the `chadmv/petri` repository, Godot 4.7).

Design: `docs/specs/2026-11-07-plume-design-brief.md` (what and why, decisions D1 to D34) and
`docs/specs/2026-11-07-plume-design.md` (how). Plan: `docs/plans/2026-11-07-plume-slices.md`.

## Commands

```bash
uv sync                                               # install (Python 3.13, Warp pinned in uv.lock)
uv run plume run recipes/smoke_puff.toml --preview    # quick look: 48 cells on the long axis, 16 frames
uv run plume run recipes/smoke_puff.toml              # full sheet
uv run plume check recipes/smoke_puff.toml            # validate, print resolved settings, no simulation
uv run pytest                                         # all tests (the gpu-marked one skips without CUDA)
uv run python -m plume.recipe.reference               # regenerate docs/recipe-reference.md
```

`--device auto|cuda|cpu` picks where kernels run; `auto` uses the GPU when there is one. The first run on a
device compiles kernels (about 20 s); later runs load them from Warp's cache.

## The iterate loop

1. Edit the recipe (every key is in `docs/recipe-reference.md`).
2. `plume run <recipe> --preview`; read the stdout summary (peak frame, fade frame, frame_m, seat).
3. Look at `out/<name>/preview/contact_grass.png` and `channels.png`; read `numbers.txt` for coverage,
   bounds and thickness per frame.
4. Change one or two values; repeat. Run without `--preview` once the look is right.

`docs/look-tuning.md` maps "what I see" to "which value to change"; add to it whenever a lesson is learned.

## Outputs (`out/<name>/`, or `--out DIR`; previews in `preview/` inside it)

`<name>.png` and `<name>.json` (the sheet and its contract), `contact_neutral.png`, `contact_grass.png`,
`channels.png`, `numbers.txt`, `settings.toml` (the resolved recipe, rerunnable), `timing.txt`. Every
file but `timing.txt` is byte-identical between two identical runs on the same machine and device.

## Conventions

- House style: American spelling; never em or en dashes (use a hyphen); descriptive names; plain language
  first, then the technical backing.
- Standalone: the repo runs anywhere, including Claude Projects and cloud sessions. Never write a
  machine-local path (a drive letter, a home folder) in code, docs or agent files; name another repository
  by its GitHub name (`chadmv/petri`) and give a path relative to its root.
- Code organization: one responsibility per file; folders by feature (`src/plume/{cli,recipe,sim,render,
  sheet,report}`); tests mirror `src/` under `tests/`; shared test helpers live in `tests/support/`.
- The recipe schema (`src/plume/recipe/schema.py`) is the single source for keys, units, defaults and
  meanings. Add a key there and regenerate the reference.
- A recipe value that becomes part of a file path is checked as a plain name in `recipe/rules.py` at load
  time (as `check_output_name` does), with a test that rejects `../`.
- Determinism: kernels only gather (each thread writes only its own cell); fixed iteration counts; all
  randomness from the recipe seed through `sim/noise.py`; host reductions in numpy. Warp runs in
  run-to-run deterministic mode (`sim/device.py`).
- Units in names (`_m`, `_s`, `_k`, `_deg`, `_mps`). Positions are meters with the origin at the center of
  the domain's floor; inside kernels, positions are in cell units from the domain's minimum corner.
- Test first where behavior is checkable. Solver and render tests run on CPU at tiny grids so the suite
  runs in CI and cloud sessions.
- Work lands as one commit per task and a pull request per slice; each slice ends with the user's look
  review and a retro in `docs/retros/`.

## Agent team

Six subagents in `.claude/agents/`: `slice-planner`, `kernel-engineer`, `pipeline-engineer`, `look-tuner`,
`code-reviewer` and `verifier`. The main session orchestrates them; `docs/agent-orchestration.md` says who
does what, in which order, and the rules every stage keeps. Every finished task gets the code-reviewer and
then the verifier before it counts as done.

## Where things live

- `docs/specs/`, `docs/plans/`: design and plans. `docs/retros/`: one per slice; read the newest first.
- `docs/backlog/`: deferred work, one file per item. `docs/look-tuning.md`, `docs/recipe-reference.md`.
- `recipes/`: example and test recipes. Game recipes live in Petri beside the effects that use them.
- `tests/golden/`: the `numbers.txt` of each approved preview; a test reruns the preview on CPU and
  compares within tolerance. After the user approves a changed look, rerun the committed recipe's
  preview into a fresh folder (`--out` a new directory) and copy that `numbers.txt` over the golden file;
  never copy from `out/`, which can hold a run of an older recipe.
