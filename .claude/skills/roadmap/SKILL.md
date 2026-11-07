---
name: roadmap
description: Use when the user types /roadmap, /roadmap deep, /roadmap <theme>, or /roadmap <theme> deep to generate or refresh the project's ROADMAP.md - a goal-aware, ordered execution plan over the open docs/backlog items. Explicit invocation only - never trigger proactively.
---

# Roadmap

Generate or refresh a single `ROADMAP.md` at the repository root: an ordered, goal-aware
view over the project's open backlog. `docs/backlog/` remains the source of truth - this
skill only orders and reports. It NEVER closes, edits, or files backlog items; that is
/backlog's job and requires the user's explicit action.

## Step 1: Preconditions

- If `git rev-parse --is-inside-work-tree` fails: respond
  `Not in a git repository - roadmap requires a project.` and stop.
- If `docs/backlog/` does not exist: respond
  `No docs/backlog/ directory - roadmap orders backlog items; capture some with /backlog first.`
  and stop.

## Step 2: Parse arguments

Tokens after `/roadmap`:

| Arguments | Mode |
|---|---|
| (none) | light full refresh |
| `deep` | deep full refresh |
| `<theme>` | light scoped refresh of one theme section |
| `<theme> deep` | deep scoped refresh of one theme section |

Theme matching: compare the token against the `(slug)` suffixes of the theme section
headers in the existing ROADMAP.md (the `## ` headers that carry a `(slug)` suffix; the
fixed headers like Now / Next / Later and Deferred have none). Exact match on the slug.
If the token matches no
slug, list the available slugs and ask the user to pick; stop until they answer. If a
theme is given but no ROADMAP.md exists yet, respond
`No ROADMAP.md yet - run /roadmap first to establish the theme set.` and stop.

## Step 3: Gather inputs (all runs)

Read, in the main conversation (no subagents):

1. **Goal docs:** the repo-root CLAUDE.md, plus any charter/spec/design documents it
   references as governing the project's current phase (read those too). If no CLAUDE.md
   exists, fall back to README.md. Distill a one-paragraph statement of the current
   goals; you will write it into ROADMAP.md.
   **The goals paragraph is a stable distillation, not a log** (~15-20 lines max): phase,
   governing docs, the active validation question(s), coarse cycle position, and hard
   requirements. Shipped events, PR numbers, and measured values belong ONLY in What
   moved / Recently shipped - never append refresh history to this paragraph. Rewrite it
   only when the goals themselves change; on most refreshes it is untouched. (Learned
   2026-08-01: unchecked appending grew it to ~95 lines of triplicate history that buried
   the goals and bred stale claims.)
2. **Open backlog:** every `docs/backlog/*.md` (top level only - skip `closed/`). From
   each: the frontmatter (title, type, status, priority, created, **`parent`,
   `blocked_by`**) plus the `## Summary` section and any `## Related` lines. Skip files
   whose frontmatter says `status: closed` and note them as misfiled.

   Build the edge graph from `parent` and `blocked_by` while reading. Resolving a
   `blocked_by` also needs `docs/backlog/closed/` - a blocker that is closed is what makes
   an item ready, so a closed blocker must be findable, not treated as dangling.

   **`## Related` wiki-links are NOT dependency edges.** They mean "see also", and most
   items carry several; treating them as dependencies invents a graph nobody authored and
   would block items on things merely mentioned beside them. Only the two frontmatter
   fields are edges.
3. **Retros:** the 2-3 most recent files in `docs/retros/`, if the directory exists.
4. **Prior ROADMAP.md**, if it exists: its generated date, theme set, ordering, and
   Deferred list.
5. **Git history:** `git log --oneline --since=<prior generated date>` (or the last ~50
   commits on a first run) to spot shipped work and the project's recent direction.

While reading, note inconsistencies for the Suggested backlog actions section - an open
item whose acceptance artifacts visibly exist per git log or named files, `status: closed`
items in the open folder, near-duplicate pairs. Report these; never act on them.

**Also collect plans whose phases were never filed.** This is the check that catches a
large plan quietly losing its structure, including plans written before any of this
existed. Report **per PLAN, not per item**:

**Skip this whole check if NO item in the project carries `parent` or `blocked_by`.** Its
output is one of the new markers, so in a project that never opted into the schema it must
not appear at all - these skills are shared across every project. The cost is that the nag
only starts once a project files its first phase item; that is the intended trade, not an
oversight. Within a project that HAS opted in, the check still reaches every plan,
including ones written long before the schema existed, which is the case it exists for.

1. For each `docs/plans/*.md` named in any open item, count its phase headings **using the
   parser specified in the `backlog` skill's Step 2.5** - the same heading pattern, the same
   `round`/`step`/`task` exclusions, the same fenced-code and line-1 guards, and the same
   pass that drops headings which are verdict records, maps, or summary duplicates rather
   than units. Do not restate a heading pattern here. Two definitions of "a phase" can
   disagree, and the disagreement shows up as a plan appearing in this report or not
   depending on which command ran.

   **Match a plan's bare FILENAME, not only a `docs/plans/` path.** Items routinely cite a
   plan in prose with no directory prefix - `plans` followed by the backticked filename
   alone. Measured on a real repo: matching only the path form missed two plans carrying
   seven phase headings, both cited by a live open bug, which is exactly the loss this
   detector exists to catch. A path-only match makes the safety net depend on citation
   style rather than on whether the work is tracked.

   Watch for one further shorthand: an item that cites a plan and then names a **sibling by
   suffix only** - the full filename, then a `+`, then a bare suffix such as
   `-phase2-addendum.md` standing in for the same date prefix. Resolve such a suffix
   against the citation it follows. This form defeats a bare filename match too, and it is
   how the second of those two plans stayed hidden.
2. **Skip files whose name ends `-execution-log`** - those record phases that already
   happened; the headings are history, not work.
3. **Skip plans whose phases are all complete - judged by any available evidence, not by
   checkboxes alone.** Unticked boxes only mean outstanding work in a plan that actually
   ticks boxes; in one that never did, they mean nothing, and this rule can then never fire,
   so the plan nags on every refresh forever. Measured: that single defect produced two of
   the three rows on one repo's live shortlist - a slice whose own umbrella item says it "is
   implemented, gated", and a plan whose closing phase was a review the user had already
   given. Before reporting, check the citing items' status and resolution
   text and the git log; if they say the work shipped, the plan is complete regardless of its
   boxes. See the `backlog` skill's Step 2.5 on establishing whether a plan's vintage ticks
   boxes at all.
4. **Skip a plan whose phases are `halted`** - built, measured, and then retired by a
   decision recorded outside the plan (a fired STOP rule, a falsified mechanism, a
   "retires" or "superseded" commit). See the `backlog` skill's Step 2.5. A halted plan is
   indistinguishable from an unfinished one by heading count and checkbox state, so without
   this it reports forever, and acting on the report re-opens work the project deliberately
   stopped. The owning item's narrative is where the decision lives - read it before
   reporting a plan whose citing item is an open bug with a long measurement history.
5. **Skip a plan if any item citing it carries a `parent`** - that means phases derived
   from this plan already exist as items, which is the thing being checked for.

   Do NOT instead ask "does the umbrella have children", because **an umbrella frequently
   does not cite its own plan.** Measured on a real repo: a migration umbrella
   mentions its own plan file zero times, while an unrelated bug cites it - so a rule
   keyed on the umbrella can never go quiet, and would nag forever about work already
   done. Phase items cite the plan their method lives in; that is the signal.

6. If a surviving plan has phase headings and no citing item carries a `parent`, report it
   once, listing every citing item and asking which is the umbrella:

   > `<plan>.md` has N phases and no item owns them. Cited by: `<item>`, `<item>`.
   > Which is the umbrella? `/backlog phases docs/plans/<plan>.md`

A citing item is not necessarily the owner - most items name a plan as background, and
several unrelated items often cite the same one. Reporting per item instead of per plan
produced four rows for one non-gap on a real repo. Ask which owns it; never guess.

If there are zero open items (the directory exists but is empty, or every item is
closed): respond `Backlog is empty - nothing to order.` and stop.

## Step 4: Deep mode only - dispatch review subagents

Skip this step entirely on light runs. On `deep` runs, dispatch read-only
subagents IN PARALLEL (one message, multiple Agent calls), then wait.

First, **discover project review agents**: scan `.claude/agents/*.md` and collect every
agent whose frontmatter sets `roadmap_review: true`, capturing its `name` and
`roadmap_focus`. Most projects have none - then dispatch only the generic
general-purpose agents below, exactly as before. When the list is non-empty, dispatch
those project agents too (see Project review agents), in the SAME parallel message as the
generic agents.

**Verify agent** (always, full and scoped runs - scoped runs pass only that theme's items):

> You are verifying backlog accuracy for the project at <repo root>, read-only - do not
> modify any files. For each backlog item listed below (path + title + summary), check
> its claims against the current code and content: does the described bug still exist in
> the source? Do its acceptance artifacts already exist (search the files it names and
> recent git log)? Classify each item: still-open, likely-shipped (cite evidence),
> stale (cite evidence), or duplicate-of <other item file>. Return a markdown list, one
> line per item, with file:line evidence for every non-still-open verdict.
> Items: <list of open item paths with titles and one-line summaries>

**Gaps agent** (full runs only):

> You are reviewing the project at <repo root> against its stated goals, read-only - do
> not modify any files. Goals: <distilled goal paragraph, plus paths of the goal docs>.
> Review the source tree and any data/content directories for problems or missing work
> that materially affects those goals and that NO existing backlog item covers. The open
> backlog titles are listed below - check against them before reporting. Return at most
> 10 findings, each with: a suggested item title, 2-3 sentences of description, file
> evidence, and which goal it serves.
> Open backlog titles: <list>

**Theme reviewer** (scoped runs only, replaces the gaps agent):

> You are deep-reviewing the <theme> subsystem of the project at <repo root>, read-only -
> do not modify any files. The theme's open items: <list with paths and summaries>. Key
> paths: <source/content paths relevant to the theme, inferred from the items>. Verify
> each item's status against the code, identify dependencies between the items, find
> subsystem problems no item covers, and recommend an execution order with a one-line
> rationale per item. Return a markdown report.

**Project review agents** (deep runs, only when agents opt in via `roadmap_review: true`):

Dispatch each discovered agent by its own `agentType` (its `name`) - NOT
general-purpose - in the same parallel message as the generic agents above. On full runs
dispatch all of them; on scoped runs dispatch only those whose `roadmap_focus` is
relevant to the named theme (match the focus phrase against the theme name and its items;
skip the rest). Give each this prompt:

> You are providing a focused roadmap review of the <roadmap_focus> aspects of the
> project at <repo root>, read-only - do not modify any files. Stay strictly within that
> focus; ignore concerns outside it (other agents cover them). Goals: <distilled goal
> paragraph, plus paths of the goal docs>. For each backlog item below that falls in your
> focus (path + title + summary), verify its claims against the current code and content
> and classify it: still-open, likely-shipped (cite evidence), stale (cite evidence), or
> duplicate-of <other item file>, with file:line evidence for every non-still-open
> verdict. Then report at most 5 problems within your focus that materially affect the
> goals and that NO existing backlog item covers, each with a suggested item title, 2-3
> sentences of description, and file evidence. Finally recommend an execution order for
> the in-focus items with a one-line rationale each. Return a markdown report.
> Items: <on full runs, all open item paths with titles and summaries; on scoped runs,
> only the named theme's items>

Fold every agent's findings into Step 5/6 ordering and into Suggested backlog actions.
Project-reviewer gap findings become suggested new items; their stale/duplicate verdicts
become close/merge suggestions. Deduplicate against the generic Verify/Gaps agents - the
overlap is intentional depth, not a reason to list a finding twice. Optionally attribute a
finding inline, e.g. `(flagged by <agent name>)`.

## Step 5: Themes

- **First run:** derive 4-8 themes by clustering the open items against the project's
  goals. Name each `<Display name> (<kebab-case-slug>)`. Prefer subsystem/outcome themes
  (e.g. solver-quality, sheet-contract, look-tuning) over type buckets (bugs, features).
- **Later runs:** the existing ROADMAP.md section headers ARE the theme set. Keep them
  stable so `/roadmap <theme>` arguments keep working. Add a new theme only when new
  items genuinely fit no existing section. Never rename or remove a non-empty theme
  without saying so in What moved.
- Every open item must land in exactly one theme section, or in Deferred (items the
  project's goal docs explicitly park).

## Step 6: Order the items

Apply these principles, in priority order, within and across themes:

1. **Goal-first.** Items advancing the project's current validation questions or stated
   phase outrank generic improvements. If the goal docs state a sequencing between
   goal areas, respect it.
2. **Corruption-before-construction.** Bugs that corrupt the thing currently being
   validated come before features that build on top of it.
3. **Dependencies.** An item never ranks above an item it depends on.
4. **Quick wins surfaced.** Cheap, high-leverage items are pulled forward and labeled
   `quick win`; effort weighs alongside importance.
5. **Deferred stays deferred.** Parked items never appear in Now/Next.
6. **Blocked items cannot lead.** An item whose `blocked_by` names anything that is not
   `status: closed` is **blocked** and may not appear in Now or Next. It still appears in
   its theme section, marked with what blocks it. An item with no `blocked_by`, or whose
   blockers are all closed, is **ready**. This applies only where the field exists; a
   project using neither field is ordered exactly as before.

Ordering is **sticky**: when a prior ROADMAP.md exists, keep its order unless an input
changed (item closed or filed, goals shifted, dependency resolved, deep-mode finding).
Record every move and its reason - they become What moved.

## Step 7: Write ROADMAP.md

Write to `ROADMAP.md` at the repo root using EXACTLY these headers (they are load-bearing
for scoped refresh and diffing):

```markdown
# Roadmap

> Generated by /roadmap on YYYY-MM-DD. Source of truth is docs/backlog/ - edit items
> there, then re-run /roadmap. Manual edits to this file may be overwritten.

<one-paragraph current-goals statement from Step 3>

## Now / Next / Later

### Now
- [<title>](docs/backlog/<file>.md) - <one line: why this, why now>

### Next
...

### Later
...

## What moved

<bullet list: shipped, new, reordered items with reasons; "First run." initially.
RETENTION CAP: keep only the ~5 most recent refresh blocks; when adding a new block past
the cap, delete the oldest and maintain a one-line pointer at the section's end noting the
trim ("Older refreshes: git log --follow ROADMAP.md and docs/retros/"). Full history lives
in git and the retros - this section is a recent-changes digest, not an archive.>

**Label each block with a plain incrementing integer** - `Refresh 7`, `Refresh 8`. Read the
most recent label and add one. **Never letter-suffix** (`30a`, `30aa`), and never start a
new numbering scheme.

This is stated because it went wrong once and the failure was invisible for ~28 refreshes.
A repo numbered its refreshes 1 to 30, then one session wrote `30b` instead of `31` and
every session after it copied the previous label's *shape* rather than the convention's
history - reaching `30ab` while never advancing to 31. The tell that it encoded nothing:
refresh `30` was marked `(light)`, exactly like all 28 lettered refreshes after it, so the
letters never marked a minor-versus-major distinction. The costs are real: `30aa` sorts
*before* `30b`, so any sort over labels misorders them; the label stops carrying "how many
refreshes ago"; and the scheme never terminates, since `30az` is followed by `30ba`.

**Infer a convention from the whole history, not the single most recent sample.** One
anomaly beside thirty regular entries is an anomaly, not the pattern - and a label copied
from the previous label is the same lossy copy chain this file warns about for derived
rollups.

**If you inherit a lettered sequence, do not renumber history.** Old labels are cross-
referenced from item rationales, tombstones and retros - one repo carried 148 such
references in ROADMAP.md alone. Resume plain integers at the next whole number above the
lettered prefix (after `30ab`, the next refresh is `31`) and leave a one-line note in the
file explaining the gap so it does not read as a lost refresh.

## Suggested backlog actions

<bullet list of close/file/merge suggestions with evidence, each ending with the
/backlog command that would perform it; omit this entire section when there are none>

## <Theme name> (<slug>)

1. [<title>](docs/backlog/<file>.md) (<type>, <priority>) - <one-line rationale>
   <optional indented line: depends on / blocks / quick win>

(repeat: one section per theme)

## Recently shipped

<items closed since the previous run, one line each; omit on first run>

## Deferred

- [<title>](docs/backlog/<file>.md) - <one-line reason it is parked>
```

- **Now, Next and Later hold bullet items only** - one `- [<title>](...) - <one line>` per item, nothing
  else. No lead paragraph or note under the `## Now / Next / Later` header or a tier header, no "what can start next" digest, no per-refresh narrative above or between
  the bullets: what shipped, unblocked or was filed this refresh goes in What moved, and readiness
  shows through the `READY` tokens and the order of the bullets. (Learned 2026-11-04: a "What can
  start next (N)" paragraph was prepended to Now on every refresh and grew to ~8,000 characters of
  stacked history from refresh 123 onward, burying the list it introduced.)
- Now/Next/Later is a **view**, not a placement: the top ~10-12 items across the three
  tiers ALSO appear in their theme sections below. Theme sections list ALL of that
  theme's open items, ordered. The Step 8 placement check counts theme/Deferred
  placement only, never the tier view - so an item appearing in both a tier and its
  theme section is correct, not a duplicate.
- **A parent renders its children as a nested markdown list.** Only when children exist;
  an item with none renders exactly as before.

  ```markdown
  - **[Umbrella title](docs/backlog/feature-....md)** `1/6 done` `next: Phase 2 - vorticity confinement`
    - `done`    [Phase 1 - multigrid pressure](docs/backlog/....md)
    - `READY`   [Phase 2 - vorticity confinement](docs/backlog/....md)
    - `READY`   [Phase 6 - extends and --set](docs/backlog/....md) `parallel`
    - `blocked` [Phase 3 - curl-noise turbulence](docs/backlog/....md) `by ...-phase-2`
  ```

  - The parent carries a **derived** rollup: `` `N/M done` `` and `` `next: <title of the
    first ready child>` ``. **Computed from the children's `status` on every refresh, never
    written by hand.** Hand-written progress prose drifts from the items it describes, and
    replacing it is the whole point of the nesting.
  - Each child starts with a status token - `` `done` ``, `` `READY` ``, `` `blocked` `` -
    so that `grep "READY" ROADMAP.md` answers "what can I start right now" across the
    entire file. Put the token first for exactly that reason.
  - A blocked child names its blocker: `` `by <slug>` ``. A child with no `blocked_by`
    among siblings that have one is marked `` `parallel` `` - that is the case a numbered
    list cannot express, and the reason a startable item otherwise reads as last in a queue.
  - Children are ordinary markdown links. **Never render the tree inside a code fence** -
    that kills the links, and the clickable path is how both a reader and a future session
    reach the item.
- **Scoped runs:** rewrite ONLY the named theme's section, that theme's entries in
  Now/Next/Later, the generated date, and What moved. Every other section must remain
  byte-for-byte identical - verify with `git diff ROADMAP.md` in Step 8.

## Step 8: Self-check (before committing)

1. Every `docs/backlog/...` link in ROADMAP.md resolves to an existing file.
2. Every open backlog item appears exactly once in a theme section or in Deferred (the
   Now/Next/Later tier view does not count as placement). Reconcile counts: open items =
   files in `docs/backlog/*.md` minus any with `status: closed` (the misfiled ones from
   Step 3). That count must equal the distinct items placed across theme sections plus
   Deferred. Investigate any other mismatch.
3. On scoped runs, `git diff ROADMAP.md` shows changes only in the named theme section,
   Now/Next/Later, the date line, and What moved.

Checks 4-6 apply only when some item carries `parent` or `blocked_by`; skip them entirely
otherwise.

4. Every `parent` and `blocked_by` slug resolves to a real item file, in `docs/backlog/`
   **or** `docs/backlog/closed/`.
5. No cycles in the `blocked_by` graph.
6. A child counts **once** for check 2, under its parent - not once nested and again as a
   top-level entry. A parent with N children still contributes N+1 placed items, so the
   reconciliation arithmetic is unchanged.

**Backward-compatibility check.** If NO item in the project carries `parent` or
`blocked_by`, the generated file must contain none of the new markers. Verify by grep, and
treat any hit as a bug in the gating rather than a curiosity - these skills are shared
across every project, and a marker leaking into a project that never opted in is the
failure mode that matters most:

```bash
# Match markers only in the POSITION they render: a nested child line starts with the
# status token, and a rollup is backticked.
grep -cE '^[[:space:]]+- `(done|READY|blocked)`' ROADMAP.md              # expect 0
grep -cE '`[0-9]+/[0-9]+ done`' ROADMAP.md                               # expect 0
```

The fourth marker - the phases-never-filed suggestion - is the one to check **by reading
the Suggested backlog actions section**, not by grep. It renders as freeform prose, and
freeform is why: one repo renders it as a markdown table headed "plans still have phases
that were never filed", while this skill's own template renders it as a sentence reading
"has N phases and no item owns them". No single pattern matches both, and writing one that
matches only the template would be the same dead-check mistake described just below. Read
the section and confirm no such entry is present.

**Match position, not just the word.** A prose-anywhere grep also matches this file's own
description of the markers - the first run of this check returned 1, and the hit was the
What-moved paragraph explaining that no marker had appeared. An instrument that matches a
readout of the thing it is measuring is not an instrument.

**Do not re-narrow the rollup grep to require a preceding bold marker.** It was written
that way once and could never fire: the rollup renders after the item's type and priority,
as in `(feature, high)` then the backticked count, not directly after a bolded link.
Measured on a repo with nine filed children, the bold-anchored form returned 0 while the
child-line grep correctly returned 9 - a compatibility guard that cannot fail is worse than
none, because it reports success in exactly the case it was built to catch.

The backtick-only form above survives the position rule for a different reason than the
child-line grep does: ROADMAP prose that discusses the marker writes it with literal
placeholder letters, so it does not match a digits-only pattern. Keep the digits in the
pattern - that is what separates a rendered rollup from prose describing one.

Fix any failure and re-check before proceeding.

## Step 9: Commit

```bash
git add ROADMAP.md
git commit -m "<message>"
```

Message: `roadmap: initial` on first run; `roadmap: refresh (<n> shipped, <n> new, reordered <slugs>)` on full refreshes; `roadmap: refresh <slug> section` on scoped runs.

## Step 10: Report

Reply in chat with: the Now list, the What moved summary, and any Suggested backlog
actions. Do not paste the whole file.

## Notes for Claude

- Light runs use NO subagents - the whole point is a cheap refresh.
- Project review agents are a deep-mode-only extension: discovered from `.claude/agents/*.md`
  (`roadmap_review: true`), dispatched by their own agentType, read-only. No opt-ins means
  deep mode is exactly the generic-agent flow.
- Never close, edit, or file backlog items from this skill, even when evidence is
  conclusive - surface the suggestion and the /backlog command instead.
- Stick to the exact template headers; downstream runs parse them.
- Use plain hyphens, never em or en dashes, in everything you write.
