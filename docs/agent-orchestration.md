# Plume agent team and orchestration playbook

How Plume is built with subagents. The **orchestrator is the main Claude session**: it talks to the user,
dispatches every subagent (subagents do not dispatch each other), commits plans and docs, owns the branch
and the pull request, and makes the final call. The agent definitions live in `.claude/agents/`; each
carries the rules it needs, so this playbook depends only on those files and `CLAUDE.md`.

## The team (6 agents)

| Agent | Model | Writes | Owns |
|-------|-------|--------|------|
| `slice-planner` | inherit | `docs/plans/` only | task plans for slices and backlog items; measured numeric bounds |
| `kernel-engineer` | opus | `src/plume/{sim,render}/`, `tests/{sim,render}/`; the Warp kernels in `src/plume/view/` (`frame_cache.py`, `viewport.py`) | Warp kernels and the code that launches them |
| `pipeline-engineer` | sonnet | `src/plume/{recipe,sheet,report,cli}/`, the rest of `src/plume/view/`, matching tests, `docs/recipe-reference.md` | recipe keys and loading, sheet contract, reports, CLI, the viewer window |
| `look-tuner` | opus | `recipes/`, `docs/look-tuning.md`, `tests/golden/` after approval | the iterate loop, look-review packages, golden refresh |
| `code-reviewer` | opus | nothing | independent review of each finished change |
| `verifier` | sonnet | nothing | the evidence gate: tests, previews, same bytes, budgets |

The orchestrator itself owns: the design interview (the `grilling` skill) and spec amendments with the
user, commits of plans, recipes and docs, the look review with the user, the pull request, the retro and
the backlog.

**Why these seams.** The code splits where its rules split: kernels live under gather-only, fixed-count,
float32 rules and are checked on tiny CPU grids; the host pipeline lives under the schema-as-single-source,
path-safety and sheet-contract rules. The look-tuner is separate from both because it uses Plume the way a
consumer does and so finds friction an author would not. The reviewer and verifier are separate from the
authors so their read is not anchored on the author's intent.

**Read-only is by instruction.** The reviewer and verifier are not granted Write or Edit, but agent
memory adds file tools so they can keep notes, and Bash can write anywhere; the others are fenced to their
folders only by their definitions. An agent editing outside its folders is a bug to report, not a
shortcut.

**Model tiers.** Each file's `model:` is a default; the orchestrator overrides at dispatch when warranted
and says so. Raise `pipeline-engineer` to opus for changes to the sheet contract, path handling or
`extends` merging; raise `verifier` to opus when diagnosing a flaky or device-dependent failure.

**Agent memory** is `memory: project`, under `.claude/agent-memory/<agent>/`. Commit memory changes with
the work that produced them, so every session and machine sees the same notes.

## Lifecycle

```
0. Intake        orchestrator + user
1. Design        orchestrator + user (grilling), only when intent is open
2. Plan          slice-planner                    -> orchestrator commits the plan
3. Build         kernel-engineer | pipeline-engineer, one commit per task
4. Review        code-reviewer, per task (or per small group of tasks)
5. Verify        verifier
6. Look          look-tuner -> orchestrator shows the user -> user rules
                 -> look-tuner refreshes golden -> verifier
7. Close         orchestrator: whole-slice review, pull request, retro, backlog
```

**0. Intake.** Classify the request:
- A slice from `docs/plans/2026-11-07-plume-slices.md` -> Plan.
- A backlog item: mechanical (bug, refactor, performance, a key whose meaning is settled) -> Plan; one
  that changes what an effect looks like or how a recipe reads, without a settled answer -> Design first.
- A look problem on an existing recipe -> Look (`look-tuner`) directly; if it finds a tool limit, that
  becomes a backlog item or a plan task.
- A question about the code -> the built-in `Explore` agent; no lifecycle.

**1. Design.** The orchestrator runs the `grilling` interview with the user and writes the outcome into the
design brief or a spec amendment. The user approves before Plan.

**2. Plan.** Dispatch `slice-planner` with the outline or backlog item. The plan names an owner per task,
marks parallel tasks, and records the probes behind every numeric bound. The orchestrator reads it, takes
any spec amendments to the user, and commits the plan before Build starts.

**3. Build.** One dispatch per task, carrying: the plan path and task id, the expected base commit, the
fast-forward recovery (`if HEAD is a strict ancestor of <sha> with no commits of its own, git merge
--ff-only <sha> and continue`), and the standing deliverable "report anything in the plan you found wrong
while executing it". When an engineer reports a plan defect, grep the plan for every instance of the wrong
claim and fix them all before the next dispatch.

**4. Review.** Dispatch `code-reviewer` with the commit range only, not the engineer's summary. Critical
and High findings go back to the same engineer (send to the existing agent so it keeps its context), then
the reviewer re-checks just those IDs. Medium and Low: fix now if cheap, otherwise file to the backlog.

**5. Verify.** Dispatch `verifier` on the reviewed commit. A FAIL goes back to the owning engineer with the
verifier's output. A task is done when the reviewer approves and the verifier passes.

**6. Look.** Every slice ends with its example recipe's look review. Dispatch `look-tuner` with the recipe,
the brief and, when the effect has one, the art reference from whoever asked for it (Plume keeps none of
its own). Send the user the package's contact sheets and channel strip with the summary, and ask the user
to judge the look in the live viewer on the PC: the message gives the command
(`uv sync --extra view`, then `uv run plume view recipes/<name>.toml`) and what to look at (motion, depth,
the inside, from which angles). A thread that launches the viewer on the PC itself (a Remote Control
session) is making a headed GPU run and takes the PC slot through the coordinator; the user launching it
needs no queue. The user rules; commit the recipe with the verdict. On approval,
dispatch `look-tuner` to refresh the golden file, then `verifier` so the golden test passes on the new
numbers. Tool friction from the package becomes backlog items.

**7. Close.** Run `code-reviewer` once over the whole slice (`main..HEAD`) and the built-in
`security-review` (it caught the `output.name` path bug in slice 1). Then the `verifier` gate on the final
commit, the pull request to `main`, the retro in `docs/retros/`, and backlog items for deferred findings.

## Routing table

| Trigger | Agent |
|---------|-------|
| A slice starts, or a mechanical backlog item is picked up | `slice-planner` |
| Plan task in `sim/` or `render/` | `kernel-engineer` |
| Plan task in `recipe/`, `sheet/`, `report/` or `cli/` | `pipeline-engineer` |
| A task's commit is ready | `code-reviewer`, then `verifier` |
| A recipe needs a look, or a look looks wrong | `look-tuner` |
| The user approved a look | `look-tuner` (golden refresh), then `verifier` |
| A test fails only on CPU or only on CUDA | `verifier` (opus) to isolate, then the owning engineer |
| Before a pull request | `code-reviewer` on `main..HEAD`, `security-review`, `verifier` |
| A broad code search | built-in `Explore` |

## Parallel work

- Tasks the plan marks parallel run at the same time, each engineer in its own worktree
  (`isolation: "worktree"`). The Agent tool creates worktrees from `main`, so every such dispatch carries
  the base commit and the fast-forward recovery above.
- Two tasks that both change `recipe/schema.py` (and so regenerate `docs/recipe-reference.md`) never run
  in parallel.
- `code-reviewer` needs no worktree and can review one task while the next is being built.
- `verifier` runs alone on the machine when timing matters: concurrent kernel compiles or runs make its
  run times meaningless.
- `look-tuner` runs on committed code only, so the look it shows matches what will merge.

## Where sessions run

- **The PC (2080 Ti):** everything, including the `gpu` tests and GPU run times.
- **Cloud and Linux sessions without a GPU:** all agents work; the verifier runs `pytest -m "not gpu"` and
  CPU previews and says "GPU not checked". GPU timing and the `gpu` tests (CPU against CUDA, and two CUDA
  runs giving the same bytes) wait for a PC run before the pull request merges. CI (`.github/workflows/ci.yml`) is the Linux CPU check.

## Hard rules every stage keeps

- **Same bytes.** Two identical runs give identical bytes in every output but `timing.txt`: kernels only
  gather, fixed iteration counts, one seed through `sim/noise.py`, host reductions in numpy float64.
- **The schema is the single source** for recipe keys; the reference is regenerated with each change.
- **Paths from input are checked** as plain names at load time, with a `../` rejection test.
- **Measure before bounding** a numerical method; the plan or test says where the number came from.
- **Golden files change only after the user approves a look**, from a fresh run of the committed recipe.
- **Plans are committed before Build**, and every input document is a claim the executing agent checks.
- **Commits:** one per task, imperative sentence with the task id; engineers commit locally, the
  orchestrator pushes and opens the pull request.
- **Style:** American spelling, regular hyphens only (never em or en dashes), plain language first.

## When to grow the team

Add an agent when a recurring kind of finding keeps slipping past the ones here, not before. Likely
candidates as the slices land:
- a **numerics reviewer** that checks a plan's written formulation (multigrid, combustion, vorticity)
  before it is built, if the code-reviewer's numerics section keeps finding scheme-level problems after
  the fact;
- a **determinism auditor** split out of the code-reviewer if scatter or reduction work (slice 6
  performance) makes that section large;
- a **Petri integration checker** that imports a sheet into Godot and compares it with the contact sheet,
  once sheets ship into the game regularly.
