---
name: retro
description: Use when the user types /retro, asks for a session retrospective or session summary saved to the project, or is wrapping up a meaningful chunk of work that future sessions will need context on.
---

# Session Retrospective

Write a structured retrospective for this session and commit it to the project.

## Step 1: Find the Prior Retro and Check for New Work

List existing retros:

```bash
ls docs/retros/ 2>/dev/null
```

**Pick the prior retro.** Take the files with the latest `YYYY-MM-DD` prefix. If more than one file shares that date, pick the one whose last commit is newest - lexicographic order is not reliable within a day (slugs sort alphabetically, and a `-2` collision suffix sorts before its unsuffixed sibling):

```bash
git log -1 --format=%ci -- docs/retros/<candidate>   # run per same-day candidate; newest wins
```

**Extract its ending SHA.** Read the prior retro's frontmatter `range:` field (format `<start>..<end>` - take the part after `..`). Older retros have no frontmatter; fall back to the `## Commit Range` section body.

**Validate the SHA.** Squash merges rewrite branch SHAs, so the recorded ending SHA may no longer exist in history:

```bash
git cat-file -e <ending-SHA>^{commit} && echo ok || echo missing
```

If missing, use the commit that added the prior retro file as the start point instead (after a squash merge, that commit contains the squashed session's work, so excluding it is correct):

```bash
git log --diff-filter=A --format=%H -1 -- docs/retros/<prior-file>
```

Call the result `<start>` either way.

**Check for new work.** Housekeeping commits do not count as new work - exclude merge commits and commits that only touch `docs/retros/` or `docs/backlog/` (the prior retro's own commit and any backlog commits always sit after its recorded range):

```bash
git rev-list --no-merges <start>..HEAD -- . ':(exclude)docs/retros' ':(exclude)docs/backlog'
git status --porcelain
```

If both are empty, output:

> "Nothing to retro - no meaningful changes this session."

Then stop.

If no prior retro exists, check whether there are any commits at all (`git log --oneline`) and any uncommitted changes (`git status --porcelain`). If both are empty, also output the nothing-to-retro message and stop.

## Step 2: Determine Commit Range

- If a prior retro exists: `<start>..HEAD`, where `<start>` is the validated ending SHA from Step 1 (or its file-add fallback).
- If no prior retro exists: use `$(git rev-list --max-parents=0 HEAD)..HEAD` (root to HEAD).

Record this range - it is written into the new retro's frontmatter so the *next* retro can find its start point.

## Step 3: Derive Topic Slug

Infer a 2-4 word kebab-case slug from the git log messages and changed files.
Examples: `auth-commands`, `scheduler-fix`, `retro-skill`, `worker-registry-refactor`

## Step 4: Write the Retro File (Draft)

Ensure `docs/retros/` exists:

```bash
mkdir -p docs/retros
```

Determine the filename: `docs/retros/YYYY-MM-DD-<slug>.md` using today's date - get it by running `date +%F`, never from memory or conversation context. If that path already exists (same-day collision), append `-2`, `-3`, etc. until the path is free. If a same-day retro would share the same slug, choose a more specific slug that reflects the *new* work instead.

Start the file with frontmatter, a TL;DR, and a Handoff section - all three always required:

```markdown
---
date: YYYY-MM-DD
topic: <slug>
branch: <output of git rev-parse --abbrev-ref HEAD>
range: <start-SHA>..<HEAD-SHA>
---

# Session Retro: YYYY-MM-DD - <Topic>

**TL;DR:** <2-4 plain-language sentences a fresh reader can understand without opening any other file>

## Handoff

<the dense, identifier-precise summary a future working session acts on without reading further>
```

The `range:` field is load-bearing - the next retro chains from its ending SHA.

**The TL;DR is written for a fresh reader** - someone who has read no spec, plan, backlog item, or
prior retro. In plain language it answers: what problem the session worked on, what changed, and
how it turned out. Session-local codenames - names coined by a spec, plan, backlog item, or test
(criterion IDs like `WL-6a`, nicknames like "the flip", labels like "Branch A", tags like
`[wl6_2x2]`) - must not appear unless glossed inline in plain words on first use. Everyday
project-domain vocabulary (recipe, emitter, contact sheet, determinism) is fine. Self-check before moving on:
would this paragraph make sense to someone who has never opened this project's docs? If any term
requires another file to decode, it belongs in the Handoff instead.

❌ `T1.7's bound fell to the measurement-first rule - SL-adv loses 16% at 400 K, so the 2% gate was the defect, not a leak.`

✅ `A test expected the simulation to keep almost all of its smoke, and the smoke puff kept losing about a sixth of it. This session showed the loss comes from the way smoke is carried along the flow, which is known to lose a little each step, not from a bug; the test now uses a limit measured on a small case.`

**The Handoff carries the density the TL;DR gave up.** It is the paragraph the next working
session acts on: spec/backlog/criterion identifiers, commit SHAs, measured numbers, and codenames
are all welcome and need no glossing - its reader is a future session with the repo open. End it
with the concrete next entry point (e.g. "next session starts at <specific item>").

**Write the TL;DR and Handoff as though the work is already pushed and merged.** The retro
commit travels in the same PR as the work, so any "not pushed yet", "no PR", "push with ... (ask
first)" or "next session starts at: asking the user to push" goes stale the moment that PR merges,
and fixing it costs a second branch, PR and merge. Say the work lands through this branch's PR
(name the branch; give the PR number only if it already exists, and never invent one), record
post-merge chores such as worktree cleanup as plain follow-ups rather than pending steps of the
merge, and make the next entry point the next piece of work. This changes only the retro's
wording: still ask the user before pushing, per the project's own rules. If the work genuinely
will not be merged (an abandoned or parked branch), say that plainly instead.

Populate the body sections from git history and session context. **The sections below are a menu, not a required skeleton - only write sections that have meaningful content.** Never write "N/A" or emit empty headers.

Available sections (include in this order when present):

```markdown
## What Was Built

## Key Decisions

## What Went Wrong and What Changes

## Recommended Backlog Items

## Files Most Touched
```

### Recommended Backlog Items

One list of the work this session surfaced but did not do - things still broken, features it
showed are needed, and questions worth deciding. (Older retros split this into `## Known
Limitations` and `## Open Questions`.) Every bullet is a task, so every bullet is a backlog
candidate at Step 5; it starts with its type tag:

```markdown
- [bug] **<title>.** <what is wrong, how it shows, where>
- [feature] **<title>.** <what is missing and why it is needed>
- [idea] **<title>.** <the open question or design lever, and what deciding it would unlock>
```

- **Tasks only, facts elsewhere.** An accepted constraint the next session merely needs to know
  ("the gate exits 0 on zero tests", "ids are creation-order keys") is not a task: if it carries a
  guard, it is a "What Went Wrong and What Changes" entry; if it is state-of-the-world context, it
  goes in the Handoff. Do not park facts here to make them visible.
- **This is backlog intake, not a priority order.** The Handoff names the next entry point and
  `ROADMAP.md` (where the project keeps one) orders the work; the order of bullets here carries no
  meaning. Add a one-line note to that effect if the list is long enough to be mistaken for a plan.
- Bullets already filed during the session keep the `- See [...](../backlog/<file>) - <summary>`
  link form and need no type tag.

### What Went Wrong and What Changes

This one section answers two questions together: *what went wrong this session* and *what will be
done differently so it does not happen again*. (Older retros split this into `## Problems
Encountered` and `## Improvement Goals`; when reading a prior retro, accept either the new heading or
those two.) A problem listed without its consequence, or a rule listed without the problem that
taught it, is incomplete.

**Entry format.** One bullet per lesson:

```markdown
- **<what went wrong, or nearly did>.** <one or two sentences: what happened, how it was caught>
  -> **What changes:** <when X, do Y, because Z>
```

- The "what changes" half is a rule the next session can act on - phrase it as a trigger
  ("when X, do Y"), not a resolution ("be more careful").
- A genuine one-off (an API outage, a typo) gets `-> No process change - one-off.` written out
  explicitly. Do not invent a rule to fill the slot.
- A lesson learned from something that went *right* is allowed when the first half states what would
  have gone wrong without it ("**A probe would have passed vacuously.** The fixture's bank anchor
  was found by search and CHECKed non-empty, which is the only reason ...").
- Facts the next session needs but that carry no rule (a trap in a tool, a gate that exits 0 on
  zero tests) are still entries; their "what changes" is the concrete guard, and they are offered
  for a *project* home (see promotion below) - a `project`-type memory or a tracked project
  file - not a `feedback` memory.

**Ledger first.** Before writing new entries, read the prior retro's section (this heading, or the
old `## Improvement Goals`) and open with one short paragraph accounting for each entry that has
not yet been promoted: *applied* this session, *recurred* (happened again), *not exercised* (the
situation did not come up), or *obsolete*. Carry a recurring lesson forward as its own bullet tagged
**(CARRIED)** instead of rediscovering it. Every unpromoted prior entry that is still a reusable
rule - applied, recurred, or not exercised alike - goes through the same promotion check below this
retro; if its home already states it, write the `[[slug]]`/home into its ledger line and drop it
from future ledgers. Entries that were already promoted (their bullet links a `[[slug]]` or says
`(promoted to <home>)`) are **not carried** - they live in their durable home now; at most, name in
one line which promoted lessons were used this session, as a signal that the home is working.
Name too any promoted memory this session found wrong or stale - a referent gone, a claim a probe
contradicted, a surface retired: it was corrected or deleted in this session, and the ledger line
says which (`corrected [[slug]]` or `retired [[slug]]`). A wrong memory is never carried; it is
fixed where it lives.

**Promotion - every reusable rule is a candidate the first time it is written.** A retro is read
by exactly one future session (the next one), so a lesson that stays in the retro has a one-session
half-life; only its durable home changes behavior. Do not wait for a lesson to recur across retros.
For each entry whose "what changes" is a reusable rule (a one-off is not), pick the durable home
by who must see it. Each home has a different reach, and the reach is the deciding fact:

- **memory** - the default for a process/behavioral rule (how work is orchestrated,
  verified, delegated, measured), written as a `feedback`-type memory; and the ONLY home for a
  machine-specific fact (an install path, an environment quirk, a tool's local configuration),
  written as a `project`- or `reference`-type memory. "Memory" means the memory directory the
  system prompt names, which is one of two stores (see **Which memory store** below); its reach
  depends on which:
  - *Project memory* (a claude.ai project thread; the system prompt says the directory is shared
    with the project). Reach: every thread and session in that project, cloud ones included.
    It does not reach Claude Code sessions run outside the project, such as a local terminal
    session on the user's PC. A machine-specific fact written here names the machine it is about
    (e.g. "on the user's Windows PC with the RTX 2080 Ti"), since most readers run in a cloud
    container. Name the machine, never a local path: the repository is cloned to different places.
  - *Local auto-memory* (a Claude Code session on one machine). Reach: this repository on this
    machine - its main session, every session in one of its git worktrees, and every subagent
    dispatched from it (the index is injected into each dispatch; the body is read on demand). It
    does not reach other projects, another machine, another clone, or a cloud session.
  Neither store is under git. A rule that must hold in every project has no promotion home: it
  still lands here, and the user copies it to `~/.claude/CLAUDE.md` by hand if they want it
  everywhere - promotion never writes that file. Cloud sessions never load `~/.claude/CLAUDE.md`,
  and project memory never reaches local sessions, so a rule that must hold in both kinds of
  session goes in the project `CLAUDE.md` as well.
  If the project already keeps a `project`-type memory that collects exactly that kind of trap
  (e.g. a build-environment memory), extending it is the better home than a new file.
- **project `CLAUDE.md`** - a rule, trap, or guard about this project's tools, gates, or workflow
  that a subagent must follow without choosing to read anything. Reach: every session, every
  subagent, and every clone, because it is loaded whole into each context - which is also why the
  rule goes in as a sentence or two, and a body that needs more lives in the tracked doc it points
  at.
  A rule that only matters when touching certain files (kernels, the sheet contract, code style)
  goes in the matching `.claude/rules/*.md` file instead (create one if none fits); it loads, for
  sessions and subagents alike, as soon as a matching file is read or edited.
- **`docs/agent-orchestration.md`** - a routing or lifecycle rule the orchestrator applies at
  intake or dispatch. Reach: only a session that follows the pointer in `CLAUDE.md`; its body is
  injected nowhere, so it is the wrong home for a rule that must change what a subagent does.
- **the owning agent's prompt under `.claude/agents/`** - a domain rule (kernels, the recipe
  pipeline, look tuning, review, verification) or a contract on that agent's own reporting. Reach: that agent on every
  dispatch, guaranteed.

**Which memory store.** Use the memory directory the system prompt names, whichever store it is;
never write to the other one. A project thread's prompt names a shared folder (e.g.
`/tmp/claude/memory/team/<name>`); a local session's names its auto-memory folder under
`~/.claude/projects/`. If the system prompt names no memory directory, or names one but gives no
way to write it, there is no memory home: skip every memory rule in this skill and offer those
lessons for project `CLAUDE.md` instead. Project memory adds three rules on top of the caps
`store_health.sh` defines:
- **One file per subject.** A later session is shown only a few files, picked by name and
  `description:`, and only each file's first 4 KB. So a new lesson extends the file for its
  subject (a kind of work, a system, a tool) as a line or two rather than starting a file per
  lesson, and a file nearing the byte cap is tightened or split by subject.
- **Shared and concurrent.** Other threads write the same folder. Re-read `MEMORY.md` (and any
  file you extend) just before editing it, keep each edit small, and read it back about ten
  seconds later; if another write replaced yours, re-apply it to the current version.
- **No secrets.** Every member of the project and every thread reads it.

Then **check whether it is already there** before offering it. Search the durable homes for the
rule's 2-3 most distinctive words:

```bash
grep -il "<kw1>\|<kw2>" <memory-dir>/*.md CLAUDE.md docs/agent-orchestration.md .claude/agents/*.md 2>/dev/null
```

(`<memory-dir>` is the memory directory named in the system prompt; if there is none, skip that
part.) Read any hit and decide:

- It **already states this rule** (same trigger, same action): the lesson is already promoted.
  Stamp the bullet with `[[slug]]` (memory) or `(already in <home>)` so it stops being carried, and
  do **not** offer it.
- It **covers the family but not this trigger** (a sibling rule with a different "when"): offer the
  lesson as `extend <slug>` - the home is that file, and Step 6 folds the new trigger into it rather
  than writing a duplicate.
- **No hit states it**: mark it a *promotion candidate* for Step 5 with a fresh home.

Lessons never go to `docs/backlog/` - they are process, not code or content tasks.

**The bar.** A candidate is promoted only if its "what changes" names a cost this session actually
paid or narrowly avoided (a wasted dispatch, a wrong number shipped, a green gate that hid a
break) and states a trigger a future session can act on. An observation with no cost behind it,
or a one-off, is not promoted; it stays in the retro.

**Store health.** Before Step 5, run the health script against the memory directory named in the
system prompt from the repository root (if there is none, skip it and every memory rule below):

```bash
bash .claude/skills/retro/store_health.sh <memory-dir> .
```

The script's header is the single definition of the index budget, the hook cap, and the body
cap. It prints them, then: the index size against the budget (exit status 1 when over), hook
lines over the cap, memory files over the cap, dangling referents (a backticked path no tracked
file matches), and memories never cited in a retro ledger since promotion. The last two are
review queues for a consolidation pass, never auto-deletes. Keep the index line and the counts
for the Step 5 message.

To populate **Files Most Touched**, run `git diff --stat <range>` and curate the top 10 files with one-line context each - do not paste raw diff-stat output.

Do **not** commit yet.

## Step 5: Present the Draft for Review (single message)

Gather everything the user needs to decide into one message: the draft location, a branch warning if applicable, and any backlog candidates.

**Branch note.** Run `git rev-parse --abbrev-ref HEAD`. If the branch is not `main` or `master`, include a warning line in the message: the retro commit will live on this branch and travel with any PR/merge/squash.

**Backlog candidates.** If `docs/backlog/` does not exist in the project, or the draft has no `## Recommended Backlog Items`, skip this part silently. Otherwise parse top-level bullet lines (lines beginning with `- ` or `* ` at column 0) inside `## Recommended Backlog Items`. Indented sub-bullets fold into the parent item's summary. Prose paragraphs are ignored.

**Skip bullets that already reference a backlog item** - any bullet whose text links into `docs/backlog/` (a markdown link like `[...](../backlog/<file>.md)` or a wiki link `[[<filename>]]`). Those were filed earlier in the session; offering them again would create duplicates.

For each detected item:
- **Type:** the bullet's leading `[bug]`, `[feature]`, or `[idea]` tag. A bullet with no tag is a drafting error - fix the draft (pick the type) rather than guessing at offer time.
- **Default title:** the first sentence of the bullet text after the tag, with leading `**bold markup**` stripped, trimmed to ~70 characters. If the bullet starts with `**Title.**` followed by detail text, use the bolded title verbatim.
- **Summary:** the full bullet text (including any folded sub-bullets), with the leading `- `/`* ` and the type tag stripped.

**Duplicate resolution - decide, do not annotate.** For each detected item, search the open backlog for keyword overlap with its default title, using the 2-3 most distinctive title words:

```bash
grep -il "<keyword1>\|<keyword2>" docs/backlog/*.md 2>/dev/null
grep -il "<keyword1>\|<keyword2>" docs/backlog/closed/*.md 2>/dev/null
```

A grep hit is a lead, not a verdict. **Read every hit** (its `title:` and body) and decide which of four cases applies. Never write "possible duplicate" or "may be a duplicate" in the offer - that hands the user a check the skill was supposed to make. When both "duplicate" and "partial overlap" seem to fit, new evidence decides: if the retro adds a measurement, a negative result, or a lead the existing item does not have, it is an append; if it adds nothing the item lacks, it is a duplicate. If two retro bullets resolve to the same existing item, merge them into one offer.

| Case | What you found | What to do |
|------|----------------|------------|
| Duplicate | An open item already tracks the same work | Do **not** offer it. Rewrite the retro bullet in place to link the existing item, in exactly the `- See [...](../backlog/<existing-file>) - <one-line summary>` form Step 6 uses for newly filed items. List it under "Already tracked" in the message so the user can override. |
| Partial overlap | An open item covers part of it, or the retro adds new evidence to it | Offer it as `[append to <existing-slug>]` instead of a new item. If accepted, Step 6 follows the backlog skill's "Updating an item" path (edit the existing file, commit `backlog: update <slug>`) rather than filing a new file. |
| Closed match | The only hit is in `docs/backlog/closed/` | Not a duplicate - it is a regression or a reopen. Offer it normally with `(closed item <slug> covered this before)` appended so the new item can reference it. |
| No overlap | No hit, or hits that on reading are about different work | Offer it normally. |

**Promotions.** From the candidates identified in Step 4 that pass the bar (each already checked against the durable homes), list each one with its home: a new memory (naming its type - `feedback` for a process rule, `project` or `reference` for a machine-specific fact), `extend <existing-slug>` for a family-match, project `CLAUDE.md`, `docs/agent-orchestration.md`, or an agent prompt. Phrase each as the trigger-shaped rule ("when X, do Y"), not the problem. Promotion is automatic: these are written in Step 6 when the user says commit, and the list exists so the user can hold one back, not so they can approve each. Mark an extend whose target is over the body cap "(will be rewritten under the cap)", and, when the index plus the new lines queued here would exceed the budget, mark each new-memory promotion "(HELD unless trims free room)". If there are none, skip this part silently. Lessons never go to `docs/backlog/`.

**The message** (omit lines that do not apply):

> Draft written to `<path>`. Review and edit the file if needed.
>
> Note: current branch is `<branch>` - the retro commit will live on this branch and travel with any PR/merge/squash.
>
> Found N items that could become backlog entries:
> 1. [bug] Sweeper still uses an independent Registry instance
> 2. [bug] `parseDurationEnv` silently falls back on garbage input (closed item `bug-2026-05-02-duration-env-parse` covered this before)
> 3. [append to `idea-2026-06-01-scoring-config`] New evidence that warm-preference scoring needs a config knob
>
> Already tracked (linked from the retro, not offered): "Sweeper leaks handles on restart" -> `bug-2026-06-03-sweeper-handle-leak`
>
> Memory store: index <bytes> of <budget> bytes (OK); 5 bodies over cap; 6 dangling referents; 13 never cited.
>
> M lessons will be promoted on commit:
> P1. When dispatching a subagent for tests, scope it to a tag, never the full suite -> feedback memory
> P2. Send every finished task through code-reviewer before verifier -> docs/agent-orchestration.md
> P3. A green report must state the passed and skipped test counts -> extend `report-skipped-gpu-tests` (will be rewritten under the cap)
>
> Reply with: **commit** or **discard**, and which backlog items to file (`all`, a subset like `1,3`, or `none`). Add `hold P2` (or `hold all`) to keep a lesson out of its home this time.

**Parse the hold answer.** Promotion needs no yes: on `commit`, every listed lesson is written in Step 6 unless held. `hold P2` / `hold P1,P3` keeps those out; `hold all` keeps every lesson out. A bare `none` or `skip` answers the backlog question only and holds nothing. Queue each lesson not held as a tuple of `(goal_text, home)` for Step 6. A hold never blocks the commit; a held lesson stays unmarked in the retro and is carried by the next one.

**Parse the response:**

- `discard` (or equivalent) -> delete the draft file and stop. Nothing is filed, so an abort leaves no orphaned backlog commits.
- Commit + `all` / `yes` -> commit the retro, file all listed items.
- Commit + a comma- or space-separated list of indices (`1,3` or `1 3`) -> commit the retro, file that subset.
- Commit + `none` / `skip` / no item answer -> commit the retro, file nothing.
- A question (e.g. "what's #2?") -> answer it, then re-present the same decision.

**Queue the accepted items** (do NOT invoke `/backlog` yet, do NOT touch the retro file yet). For each, record a tuple of:

- `type` (`bug`, `feature`, or `idea`; or `append` for a partial-overlap item, with the existing filename)
- `title` (string)
- `summary` (string - full bullet text with sub-bullets)
- `original_bullet_line` (the exact line in the retro draft, used later to locate-and-replace)

**Wait for the user's reply before proceeding.**

## Step 6: Commit the Retro

If Step 5 queued any backlog items, drain the queue first - invoking the `/backlog` skill once per item, in queue order. This delegates slug derivation, file structure, frontmatter, and the per-item commit to the centralized `/backlog` skill rather than duplicating those concerns here.

For each queued tuple `(type, title, summary, original_bullet_line)`:

**If `type` is `append`** (a partial-overlap item accepted at the offer): do not create a new file. Follow the backlog skill's "Updating an item" path - fold `summary` into the existing item's `## Notes` (or `## Related`) section, keep its frontmatter valid, and commit it as `backlog: update <filename-without-extension>`. Then replace `original_bullet_line` in the retro draft with the same `- See [...]` link form as step 3 below, pointing at the existing file. Skip steps 1-2.

**Otherwise:**

1. Invoke the `/backlog` skill via its terse path:

```
/backlog <type> <title> -- <summary>
```

Use the `Skill` tool with `skill: "backlog"` and `args: "<type> <title> -- <summary>"`. The backlog skill's terse path uses the supplied summary verbatim with no draft-confirmation step, but its duplicate check still runs. If that check flags a file that Step 5 already read and ruled out (or a closed item the offer already noted), proceed without re-asking - the decision was made at the offer. If it flags a file Step 5 never read, read it now and apply the same four-case rule; only ask the user if it is genuinely ambiguous.

2. The skill writes the file, commits it (`backlog: add <filename-without-extension>`), and reports `Filed: docs/backlog/<filename>`. Capture that filename.

3. Replace `original_bullet_line` in the retro draft (use the Edit tool) with:

```markdown
- See [`<filename-without-extension>`](../backlog/<filename>) - <title>
```

(Path is relative to `docs/retros/`. The link target is the file `/backlog` just committed, so the link resolves immediately.)

**Drain the promotion queue.** For each `(goal_text, home)` tuple not held in Step 5, write the lesson to its durable home under the caps `store_health.sh` defines:

- **Memory** (the default for process rules, and the only home for machine-specific facts): write a memory file of the type chosen in Step 4 per the memory system and add its one-line `MEMORY.md` index entry, kept under the hook cap. A memory that asserts how a tool or the harness behaves carries `verified: <today>` in its metadata so a later pass can find claims that have aged. For an `extend <slug>` home, edit that existing memory instead of creating a file: fold the new trigger into the rule's existing body and, if needed, its `description:`. If the file is over the body cap, or the extend would take it over, rewrite the file so every trigger fits under the cap - never append another section. If two triggers genuinely cannot share one file under the cap, the lesson is a new sibling file and the two link each other with `[[slug]]`. The memory directory lives outside the repository - do **not** commit memory files.
- **Index budget.** Before writing any new memory file, compute the index size the queued new files would produce. If it exceeds the budget: first trim the hook lines the script listed over the cap (a `description:`/index edit each, cut to the rule's trigger and action); if still over, hold the remaining new-file promotions in queue order and name the `consolidate-memory` skill in the report as the pass that makes room. Never raise the budget in the script to fit a promotion - a crossing is answered by trimming or merging - and if you raise it anyway, say so in the report. Extends and tracked-file homes add no index line and are never held for budget.
- **`CLAUDE.md` / a `.claude/rules/` file / `docs/agent-orchestration.md` / an agent prompt**: make the edit in place, as a sentence or two stating the trigger and the action. Commit every tracked-file promotion together, BEFORE the retro commit, as its own commit `docs: promote retro lessons`, so the edits are reviewable apart from the retro. Promotion never writes the user-level `~/.claude/CLAUDE.md`.

In the retro draft, append `(promoted to <home>)` to the corresponding "What Went Wrong and What Changes" bullet - and, when promoted to a memory, link the memory slug as `[[slug]]` - so the next retro sees it as institutionalized and drops it from the ledger instead of carrying it. Lessons held - by the user or by the budget - stay unmarked and are carried by the next retro as normal.

After all queued items are drained (or immediately, if the queue was empty), commit the retro:

```bash
git add docs/retros/YYYY-MM-DD-<topic>.md
git commit -m "docs: add session retro YYYY-MM-DD-<topic>"
```

The git log on the branch will read:
```
backlog: add <slug-1>
backlog: update <slug-2>
...
docs: promote retro lessons
docs: add session retro YYYY-MM-DD-<topic>
```

- matching the per-item commit convention used everywhere else `/backlog` is invoked.

**Report** (one message after the commit; omit lines with nothing to say). Every promotion is a
write the user did not individually approve, so this is where they see it:

> Committed `docs/retros/<file>` as `<sha>`.
> Filed: `<backlog-file>`, `<backlog-file>` (or: no backlog items filed).
> Promoted: P1 -> [[slug]] (new); P3 -> extend [[slug]] (rewritten under the body cap); P2 -> `docs/agent-orchestration.md` (commit `<sha>`).
> Held: <lesson> - index over budget after trims; run the `consolidate-memory` skill to make room.
> Trimmed hooks: <slugs>. Corrected or retired memories: <slugs>.
> Memory store: index <bytes> of <budget> bytes.

## Step 7: Ensure Session-Continuity Directive (project-level, one-time)

The directive lives in the project `CLAUDE.md`, not `~/.claude/CLAUDE.md`, so that cloud sessions
and other clones (which never load the user-level file) also read the latest retro. Check for it:

```bash
grep -qi "Session continuity" CLAUDE.md 2>/dev/null && echo "already present" || echo "needs update"
```

If it is **not** present, add this section to the project `CLAUDE.md` (create the file if it does
not exist), then commit it on its own as `docs: add session-continuity directive`:

```markdown

## Session continuity

At the start of each session, read the most recent file in `docs/retros/` for context on prior work.
```

If it is already present, skip this step.
