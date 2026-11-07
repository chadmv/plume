---
title: Slice 2 - solver quality and iteration tools
type: feature
status: open
created: 2026-11-07
priority: high
source: build plan docs/plans/2026-11-07-plume-slices.md, slice 2 outline
parent: feature-2026-11-07-plume-first-version
blocked_by: [feature-2026-11-07-slice-1-smoke-puff-end-to-end]
---

# Slice 2 - solver quality and iteration tools

## Summary
Bring the solver up to the brief (multigrid pressure, vorticity confinement, curl-noise turbulence, wind
and drag, the CFL substep cap) and add the recipe variation tools (`extends`, `--set`) that make the
agent's iterate loop fast. The puff gains billows instead of rolling into a dome, and preview and final
runs look alike.

## Proposal
Write the slice's task plan from the outline first. Scope from the outline and the brief:
- [ ] Geometric multigrid behind `pressure.solve`, fixed V-cycles per step (D7, A3 `[solver]`)
- [ ] Vorticity confinement scaled with cell size (D9, D30)
- [ ] Seeded curl-noise turbulence: scale, strength, speed, in meters (D9)
- [ ] Constant wind and drag (D9)
- [ ] CFL substep cap with deterministic arithmetic; resolved count in the log (D10)
- [ ] `extends = "<parent>.toml"` (one parent, deep-merged) and `--set key=value`; both resolved into
      `settings.toml` (D23, D27)
- [ ] Look review of the puff with turbulence, preview against final; regenerate the golden file from a
      fresh run after approval

## Acceptance / Done When
- The user approves the turbulent puff and preview and final runs look alike.
- Determinism and CPU against GPU tests still hold; the golden file is refreshed from a fresh run.
- A retro in `docs/retros/`.

## Related
- `docs/plans/2026-11-07-plume-slices.md` (Slice 2)
- [[idea-2026-11-07-advection-loses-small-puff-smoke]] (weigh with this slice's solver work)
- `src/plume/sim/pressure.py`, `src/plume/sim/forces.py`, `src/plume/sim/stepper.py`,
  `src/plume/recipe/load.py`, `src/plume/cli/main.py`
