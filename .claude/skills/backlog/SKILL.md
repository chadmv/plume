---
name: backlog
description: Capture forward-looking work - bugs, features, ideas - into per-item files in the project's docs/backlog/ directory so future sessions can find and act on them. Invoke when the user types /backlog, /backlog list, or /backlog close. ALSO use proactively to offer a backlog entry when the user defers work mid-conversation ("we should...", "TODO", "that's a bug, but not now", "let's circle back to..."), when you notice during code review or debugging that something is broken or suboptimal but out of scope for the current task, or when a retro draft includes Recommended Backlog Items (Open Questions / Known Limitations in older retros) not yet captured. Never auto-file without confirmation; never offer for the current task; never offer twice for the same item in one session; high-confidence specific items only.
---

# Backlog

Capture, list, and close forward-looking items in the active project.

## Step 1: Determine the operation

Parse the slash arguments after `/backlog`:

- No arguments, or first token is `bug`, `feature`, or `idea` → **capture** (Step 2).
- First token is `list` → **list** (Step 6). Optional filter (`bug`, `feature`, `idea`, `closed`, `all`) handled inside Step 6.
- First token is `close` → **close** (Step 7).
- First token is `doctor` → **doctor** (Step 8).
- First token is `phase` → **capture one child** (Step 2, with `parent` prefilled from the second token, which is a fragment matching the parent item).
- First token is `phases` → **capture children from a plan** (Step 2.5). The second token is a path to a plan document.
- Anything else → respond `Unknown subcommand. Use /backlog [type] [title], /backlog list [type|all], /backlog close <fragment>, /backlog phase <parent> <title>, /backlog phases <plan-file>, or /backlog doctor.` and stop.

## Step 2: Capture - gather fields

Three invocation forms; choose based on the slash arguments:

- **Interactive** (`/backlog` with no args): ask the user for type, title, optional priority, and a 1-3 sentence summary, one prompt at a time.
- **Fast path** (`/backlog <type> <title>`): infer summary from recent conversation context (last few user/assistant turns or recent tool output). Show a draft and ask for confirmation before writing.
- **Terse path** (`/backlog <type> <title> -- <summary>`): use the inline summary verbatim. No confirmation step unless the type is invalid. Slug collisions are resolved silently by appending `-2`, `-3`, etc. (see Step 3).

Validate that `<type>` is one of `bug`, `feature`, `idea`. If not, ask the user to pick one.

Optional fields to gather (skip if not offered):
- `priority`: `low`, `medium`, or `high`.
- `source`: a short note on where the idea came from (e.g. "noticed while debugging worker registry"). Inferred from context if obvious, otherwise omitted.

## Step 2.5: Capture children from a plan (`/backlog phases <plan-file>`)

A large plan divides into phases meant to span several sessions. Those phases live in the plan
document, which `/roadmap` never reads - so they are invisible where work is ordered, and they get
forgotten. This turns them into items.

**This parser is SHARED with the retro-discovery pass over historical plans. Do not write a second
one.** Two definitions of "a phase" can disagree, and the disagreement shows up as items appearing or
not appearing depending on which command was run.

1. Read the plan file. Collect every heading matching, case-insensitively:

   `^#{1,3}\s+(sub-)?(phase|slice|stage)\s+[0-9A-Za-z]`

   **Level 1 is included, but only with both guards below.** Some plans put their real units at
   `#` - measured on one repo, eleven of them across three plans (`# STAGE 1`, `# PHASE A`,
   `# Sub-stage 1`), every one invisible to a `#{2,3}` pattern. Matching level 1 naively is worse
   than not matching it: on that same corpus it also pulled in **14 wrapped code comments** that
   begin with `#` inside fenced code blocks, plus 4 plan titles.

   - **Skip line 1.** A level-1 heading on the first line is the plan's title. The plan is not a
     unit within itself.
   - **Skip anything inside a fenced code block**, and close a block at the next fence marker
     **or at the next `##`/`###` heading, whichever comes first.** Do not track fences by parity
     alone: a single unbalanced fence inverts every parity count after it, and that is not
     hypothetical - one measured plan opens a `cpp` fence it never closes, which made 8 genuine
     phase headings look like they were inside code. Bounding a block at the next real heading
     confines that damage to a few lines. Verified on the same corpus: this finds 10/10 real
     level-1 units, leaks 0 comments, and changes nothing about which `##`/`###` headings match.

2. **`round`, `step` and `task` are deliberately EXCLUDED, and this is the one non-obvious rule.**
   - `round` names measurement iterations in experiment logs (`## Round 2 - recovery_multiplier
     sweep`). Measured on one real repo: it matched 11 headings and every single one was an
     experiment, not schedulable work. A naive alternation would file 11 phantom items.
   - `step` and `task` are the sub-tiers that belong as checkboxes INSIDE a phase item, not as items.

3. **Now READ each surviving heading and drop the ones that are records rather than units.** The
   regex cannot do this, and the obvious mechanical shortcut is falsified below. Three kinds recur:

   - **A verdict or result record** - `## Phase B verdict: (record here on completion)`,
     `## Phase A verdict: COMPLETE (recorded 2026-07-12)`, `## Phase 2A gate (Task 32) - PASS`,
     `## Phase 1.5 measurements`. The body records an outcome, or is an empty placeholder waiting
     for one. It proposes no work.
   - **A map or index** - `## Stage map and the control arm at each stage`, `## Sub-stage map`. It
     summarises units defined elsewhere. The tell: another heading in the same file names the same
     units and carries their real bodies.
   - **A summary duplicate of a unit at another level** - a plan lists `## Phase A` / `## Phase B`
     as a short phase map near the top, then defines the real `# PHASE A` / `# PHASE B` sections
     further down. Count the unit once, at the heading with the real body.

   **Do NOT suppress on "no checkboxes and no sub-headings" instead.** It is the tempting
   mechanical proxy and it was dry-run and falsified: on one repo it correctly killed every record
   above, but it also killed three genuinely deferred phases
   that were correctly filed as real items and are exactly what `unelaborated` exists to
   describe. A deferred phase and an empty verdict placeholder look identical by that measure.

4. For each heading, derive a title from the text after the number, and read that phase's body for
   its `- [ ]` / `- [x]` checkboxes.

5. Classify each phase:
   - **done** - every checkbox ticked.
   - **unfinished** - some unticked.
   - **unelaborated** - it has NO checkboxes at all. A phase with no steps is not unfinished work, it
     is *undesigned* work (plans often defer a late phase to its own future plan). Label it as such
     in the offer and do not present it as immediately actionable.
   - **halted** - the work was built, measured, and then RETIRED by a decision recorded somewhere
     other than the plan. List it with the others so the reader sees it was considered, labelled
     `halted` and naming the decision, but do not offer it for filing: filing it re-opens work the
     project deliberately stopped, against an item whose body is the record of why it stopped.

   **`halted` is invisible in the plan file, so you must look outside it.** A halted phase and an
   unfinished one are identical on every mechanical signal: unticked boxes, some named artifacts
   missing, an open citing item. The difference lives in the owning item's narrative and in the git
   log. Before classifying ANY phase as unfinished, check both for a stop decision - a fired
   pre-registered STOP rule, a falsified mechanism, a "retires" or "superseded" commit. Measured on
   a real repo: three plans holding eleven units were all retired by their own pre-registered STOP
   rules (each retiring commit said so in its subject), and
   every one of them scanned as plain unfinished work. In a project that pre-registers stop rules
   this is common, not an edge case.

   **Checkbox state can be worthless.** If a project adopted checkbox-ticking only recently, older
   plans show 0 ticked regardless of what shipped - one real repo measured 0% ticked across 178 plans
   before a convention change.

   **Find the convention's start DATE, and do it by counting plans, not boxes.** On that same repo
   the month-level aggregate said 18% of one month's boxes were ticked, which reads as "this month is
   trustworthy". Counting plans instead: only 5 of that month's 24 ticked anything, and four of those
   five fell after a single date. The convention began on that date, not that month, and checkbox
   state carried information for **4 plans out of 202** rather than the 23 the aggregate implied. A
   ticked-box percentage is dominated by whichever few plans adopted the convention, so it tells you
   nothing about the plan in front of you. Before trusting the classification, check whether plans of
   this plan's own vintage tick boxes at all; if not, say the classification is unknown rather than
   calling finished work unfinished.

6. **Check whether an existing item already covers each phase, BEFORE offering to file it.**
   Filing a phase whose work is already tracked creates a duplicate, and a duplicate in a
   dependency graph is worse than one in a flat list because both copies accumulate edges.

   - Plans often say so outright. A `**Closes:** <existing item>` line under a phase heading names
     the item that phase would duplicate - read it and follow it.
   - Otherwise run the ordinary Step 3 duplicate check against the phase's title.

   When an existing item is found, offer three resolutions rather than filing blindly:

   - **Adopt** - the existing item BECOMES the phase child: add `parent` and `blocked_by` to it
     instead of creating a new file. Right when the item and the phase are the same work.
   - **Adopt and re-scope** - the item is broader or narrower than the phase. Say exactly how, and
     let the user decide whether to adopt, split, or leave it out of the tree.
   - **Skip** - the phase is already covered and needs no item.

   **An existing item may span SEVERAL phases**, which single-valued `parent` cannot express. Do not
   quietly pick one. Report the span and ask; adopting into the wrong phase silently misplaces the
   work in the schedule, which is the failure this whole schema exists to prevent.

7. Present the full list - each phase with its classification, and each already-covered phase with
   the existing item and the proposed resolution - and **ask which to file. Never file without
   confirmation.** Every signal above is a heuristic, and a wrong one creates a file plus edges.

8. For each accepted phase, file it via Steps 3-5 with:
   - `parent:` set to the umbrella item (ask which item that is if it is not obvious; a plan is often
     *cited* by several items but *owned* by one).
   - `blocked_by:` set to the previously accepted sibling. **Offer that chain, never assume it** - a
     plan may declare a phase parallelizable (e.g. a heading saying "parallelizable from Phase 0
     onward"), and such a phase takes no `blocked_by` at all. Getting this wrong is what makes a
     startable phase look eighth in a queue.

## Step 3: Capture - derive slug and resolve filename

1. Lowercase the title.
2. Replace any non-alphanumeric character with `-`.
3. Collapse runs of `-` into a single `-`; trim leading/trailing `-`.
4. Take the first 2-6 meaningful words (drop stop-words like `the`, `a`, `for`, `in`, `to`, `of`, `and`). Prefer a longer, more specific slug over a short ambiguous one.

Filename: `docs/backlog/<type>-YYYY-MM-DD-<slug>.md` using today's date. Get the date by running `date +%F` - do not rely on memory or conversation context for it.

Same-day collision: if the path already exists, append `-2`, `-3`, etc. until the path is free. If a same-day item shares an exact slug, prefer choosing a more specific slug that reflects the new item.

```bash
mkdir -p docs/backlog
```

**Duplicate check (all three invocation forms, terse path included - skipping the confirmation step never means skipping this check):** before writing, search existing items for keyword overlap with the new slug:

```bash
grep -il "<keyword1>\|<keyword2>" docs/backlog/*.md 2>/dev/null
```

Use the 2-3 most distinctive slug words as keywords (matches filenames via `-l` plus titles and bodies via `-i`). If any hit looks like it covers the same work, show the candidate(s) with their `title:` lines and ask: `Possibly a duplicate of <file>. Still file?` If the user confirms, continue; if it is a true duplicate, offer to append the new context to the existing item instead (see "Updating an item"). No plausible hits → proceed without asking.

## Step 4: Capture - write the file

Write the file with this structure:

```markdown
---
title: <one-line summary>
type: <bug|feature|idea>
status: open
created: YYYY-MM-DD
priority: <low | medium | high>      # omit field entirely if not specified
source: <short note>                  # omit field entirely if not specified
parent: <slug>                        # omit unless this item is PART OF a larger one
blocked_by: [<slug>, <slug>]          # omit unless hard-blocked by other items
---

# <title>

## Summary
<1-3 sentences. The "what" and "why this matters". Always required.>
```

**`parent` and `blocked_by` are OPTIONAL and omitted by default.** A slug is a filename without
`.md`. `parent` is single-valued and means "this item is one part of that larger item" - a phase of a
plan, a stage of a migration. `blocked_by` lists items that must reach `status: closed` before this
one is workable.

**Never store a `blocks` field.** It is the exact reverse of `blocked_by`, and storing both creates
two halves that can drift apart. Anything needing "what does this block?" derives it by scanning for
items whose `blocked_by` contains this slug.

Most items have neither field. Add them only when the structure is real: a body of work genuinely
split into separately schedulable parts, or a hard ordering constraint. A vague "related to" belongs
in `## Related` as a `[[wiki-link]]`, not in `blocked_by`.

Add additional sections from this menu **only if they have content**. Never emit empty headers.

```markdown
## Context
<Where this came from, what surrounding work prompted it, links to retros or commits.>

## Repro / Symptoms          ← bugs only
<Steps, observed vs expected behavior, error messages.>

## Proposal                   ← features mostly; sometimes ideas
<Sketch of the approach. Not a full design - that is brainstorming's job.>

## Acceptance / Done When
<How we will know it is resolved. Bullet list.>

## Related
<Source files with paths, retro references, and related backlog items as wiki-style
links: [[<filename-without-extension>]]. Always use the [[...]] form for backlog
cross-references - it is greppable and future sessions resolve it to the file.>

## Notes
<Anything else worth keeping.>
```

## Step 5: Capture - commit

```bash
git add docs/backlog/<filename>
git commit -m "backlog: add <filename-without-extension>"
```

Then report the path to the user:

> Filed: `docs/backlog/<filename>`

## Step 6: List

`/backlog list [type|all]` - list open items in the project.

If `[type]` is `bug`, `feature`, or `idea`, glob `docs/backlog/<type>-*.md`; if `closed`, glob `docs/backlog/closed/*.md`; otherwise glob `docs/backlog/*.md` (top level only).

Extract all frontmatter in a **single bash pass** - never read the files one at a time:

```bash
awk 'FNR==1{print "FILE:" FILENAME} /^(title|type|priority|created|parent|blocked_by):/{print} FNR>9{nextfile}' docs/backlog/*.md
```

**Children render under their parent.** An item whose `parent` names another open item is listed
indented beneath it rather than as a top-level row, in `blocked_by` order. A parent plus its children
counts as **one** entry against the 30-row cap, so a nine-phase umbrella does not consume a third of
the view.

Compute age in days from `created` to today (`date +%F`).

Output, in order:

1. A one-line summary: `71 open: 17 bugs / 38 features / 16 ideas. Oldest: 28d.`
2. A compact table, sorted by priority descending (`high`, `medium`, `low`, none), then by age descending:

```
| type    | title                                  | priority | age |
|---------|----------------------------------------|----------|-----|
| bug     | gRPC stream concurrent-send race       | high     | 3d  |
| feature | Perforce multi-workspace support       | medium   | 1d  |
| idea    | Rolling retro summary                  | -        | 0d  |
```

If there are more than 30 rows and no filter was given, show the top 30 and end with: `...and N more. Narrow with /backlog list <type>, or /backlog list all for everything.` `/backlog list all` always shows the full table.

If no files are present, say `Backlog: 0 open.` (or `No open <type> items.` when a type filter was specified) and stop.

## Step 7: Close

`/backlog close <fragment> [resolution]` - mark an item resolved.

**Closing a batch? Run this full flow once per item.** Do NOT invoke `/backlog close` for the
first item and then hand-repeat the `git mv` / frontmatter / commit commands for the rest from
memory - hand-rolling a multi-step procedure across several items is how the step-4 move silently
gets dropped. Each close is the whole flow (steps 1-9), including the move to `closed/` and the
step-8 verify. The move is the operation that matters; the frontmatter stamp without it is the bug.

1. Find a single matching open file via case-insensitive substring match against filenames in `docs/backlog/`:

```bash
find docs/backlog -maxdepth 1 -name "*.md" 2>/dev/null | grep -i "<fragment>"
```

  If the filename match yields zero results, fall back to matching `title:` lines (slugs drop stop-words, so a title word may not appear in the filename):

```bash
grep -il "^title:.*<fragment>" docs/backlog/*.md 2>/dev/null
```

  - Zero matches from both: respond `No open backlog items match "<fragment>".` and stop. Note: only files in `docs/backlog/` (not `docs/backlog/closed/`) are candidates. Already-closed items cannot be re-closed.
  - Multiple matches: list them and ask the user to pick one.
  - Exactly one match: proceed.

2. **Check the edges before closing.** Both are warnings, not refusals - the user decides:

```bash
grep -l "^parent: <slug>" docs/backlog/*.md 2>/dev/null                    # open children
grep -l "blocked_by:.*<slug>" docs/backlog/*.md 2>/dev/null                # items this blocks
```

   - Open children exist → warn: `<slug> still has N open children: <list>. Close it anyway?` An
     umbrella closed over open children looks finished while its work is outstanding, which is
     exactly the state `doctor` reports as malformed.
   - Items name it in `blocked_by` → note what this frees: `Closing this unblocks: <list>.` No
     confirmation needed; it is good news and worth saying.

3. Resolve `[resolution]` (default `fixed`). Must be one of `fixed`, `wontfix`, `duplicate`, `obsolete`. If invalid, ask the user.

4. If the user did not provide a one-line resolution note inline, ask: `Resolution note? (1-2 sentences, optional commit SHA)`. Use the response as the note.

5. Move the file:

```bash
mkdir -p docs/backlog/closed
git mv docs/backlog/<filename> docs/backlog/closed/<filename>
```

6. Update the moved file's frontmatter:
   - Set `status: closed`.
   - Add `closed: YYYY-MM-DD` (today's date).
   - Add `resolution: <fixed|wontfix|duplicate|obsolete>`.

7. Append to the body:

```markdown

## Resolution
<note>
```

8. **Verify before committing.** This flow has historically dropped steps - most damagingly the
   move in step 5, leaving an item stamped `status: closed` but stranded in the OPEN dir, which
   `/backlog list` and `/backlog doctor` then report as malformed. Run BOTH checks before you
   commit:

```bash
# (a) the closed copy has all four markers - must print 4
grep -c "^status: closed\|^closed: \|^resolution: \|^## Resolution" docs/backlog/closed/<filename>
# (b) the item actually LEFT the open dir - must print nothing
ls docs/backlog/<filename> 2>/dev/null && echo "STILL IN OPEN DIR - the git mv (step 5) did not happen"
```

   Check (a) must be 4 and check (b) must print nothing. If (a) is short, fix steps 6-7; if (b)
   prints a path, the move was skipped - do the `git mv` in step 5. Do not commit until both pass.

9. Commit:

```bash
git add docs/backlog/closed/<filename>
git commit -m "backlog: close <filename-without-extension>"
```

10. Report:

> Closed: `docs/backlog/closed/<filename>` (<resolution>)

## Step 8: Doctor

`/backlog doctor` - check every backlog file against the format invariants and offer repairs.

1. Check **open items** (`docs/backlog/*.md`): frontmatter has `title`, `type`, `status: open`, `created`; **`type` is one of `bug`, `feature`, `idea`**; and the `type` field matches the filename prefix.

   **Check the VALUE against the vocabulary, not just its agreement with the prefix.** These are two
   different checks and the second does not imply the first: a file named `task-foo.md` declaring
   `type: task` is perfectly self-consistent, so a prefix-agreement check passes it in silence.
   Measured on a real repo: two items carried an invalid `task-` prefix, and doctor reported only the
   one whose `type` field happened to disagree with its filename - the genuinely invalid pair sailed
   through every run until a human noticed the word `task` was not on the list. A validity check that
   only compares a value to itself is not a validity check.

   Repairing one is a **rename**, not a field edit: `git mv` the file to the correct prefix, fix the
   `type` field, and sweep every reference to the old slug - `[[wiki-links]]`, ROADMAP.md links,
   plans, retros, and any `parent` / `blocked_by` naming it. The slug is the item's identity, so a
   rename that skips the sweep trades one doctor finding for several dangling ones.
2. Check **closed items** (`docs/backlog/closed/*.md`): frontmatter has `status: closed`, `closed: YYYY-MM-DD`, and `resolution:` with a valid value; body has a `## Resolution` section; and **the same `type` vocabulary and prefix-agreement checks as invariant 1**.

   Closing an item does not make its frontmatter correct, and the common cause here is real: an item
   filed as one type is re-typed as another during its life (an `idea` that becomes a `feature`) and
   the FILE is never renamed to match. Report these, but weigh the repair - a closed item is
   historical and its slug is usually cited from retros, specs and sibling items, so the rename's
   reference sweep can cost far more than the finding. Reporting without renaming is a legitimate
   outcome for a closed item; say so rather than leaving it silently unreported.

3. Check **edges** across all items, open and closed. Skip this entirely if no file carries `parent`
   or `blocked_by` - a project not using them has no edges to check, and an absent field is not a
   dangling one:

   - **Dangling `parent`** - the named slug has no file in `docs/backlog/` or `docs/backlog/closed/`.
   - **Dangling `blocked_by`** - same, per entry in the list.
   - **Cycles** - follow `blocked_by` transitively and report any item reachable from itself. Report
     **every member of the cycle**, not just the item you noticed it from; one name is not actionable.
   - **Closed parent, open children** - a closed item that OPEN items still name as `parent`. This is
     the state that makes a body of work look finished while its parts are outstanding.

```bash
grep -l "^parent:\|^blocked_by:" docs/backlog/*.md docs/backlog/closed/*.md 2>/dev/null | wc -l
```

Run the checks with bash (grep per invariant across each directory), not by reading files one at a time.

4. Report findings grouped by file, e.g. `closed/bug-...-foo.md: missing resolution field, missing ## Resolution section`. If everything passes, say `Backlog: all N files pass.` and stop.
5. Offer to repair. On accept:
   - Mechanical gaps (wrong `status`, missing `closed:` date) - fill from the file's location and its `git log` history (the close commit's date).
   - Judgment gaps (missing `resolution:` value or `## Resolution` note) - propose a value inferred from the close commit message or file content, but show the proposed repairs and get confirmation before writing. Never invent a resolution silently.
   - Commit all repairs as one commit: `backlog: doctor repairs`.

## Updating an item

There is no `update` subcommand. To re-prioritize, append new evidence, or extend an existing item: edit the file directly (keep the frontmatter valid), then commit with the matching message convention:

```bash
git add docs/backlog/<filename>
git commit -m "backlog: update <filename-without-extension>"
```

When a capture turns out to be a duplicate (Step 3 check), this is the path: fold the new context into the existing item's `## Notes` or `## Related` and commit as an update.

## Proactive-offer rules

You are AUTHORIZED and ENCOURAGED to offer a backlog entry when you detect deferred work during normal conversation, but you MUST follow these rules:

1. **Never offer for things the user is currently working on.** The current task is not deferred work. If the user is actively asking you to fix or implement something, just do it - do not interrupt to file a backlog entry.
2. **Never offer twice for the same item in one session.** Track offers mentally for the duration of the session. If the user dismisses an offer, do not nag.
3. **High confidence only.** Vague observations like "this could be cleaner" do not qualify. The item must have a specific, actionable shape - a recognizable bug, a concrete feature outline, or a defined question.
4. **Never auto-file without confirmation.** All proactive captures require an explicit user accept. The user dismisses by saying no, ignoring, or moving on.

**Triggers** (use judgment, these are signals not rules):
- User says "we should...", "TODO", "that's a bug, but not now", "let's circle back to...", "remind me to...", "for later".
- During code review or debugging, you notice something broken or suboptimal that is clearly out of the current task's scope.
- You are drafting a retro and an item belongs in `## Recommended Backlog Items` (`## Open Questions` / `## Known Limitations` in older retros) but is not yet a backlog entry.

**Offer format** - a single short message, nothing else:

> Want me to file this as a backlog `<type>` item? - `<draft title>`: <one-sentence draft summary>

The one-sentence summary lets the user judge the offer without asking follow-ups; keep it to a single line.

If the user accepts, capture via the fast-path flow (Step 2 fast path), inferring summary from the surrounding context. If the user dismisses, drop it silently.

## Notes for Claude

- The `description` field in frontmatter is what triggers this skill. Read it carefully - it lists every signal that should make you invoke `/backlog` proactively.
- Always commit each capture and each close as its own commit. The git log of `docs/backlog/` is itself a useful artifact.
- Never read backlog files at session start unless the user asks.
- This skill is project-scoped. If `git rev-parse --is-inside-work-tree` fails, respond `Not in a git repository - backlog requires a project.` and stop.
