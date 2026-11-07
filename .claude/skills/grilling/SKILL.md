---
name: grilling
description: Relentless design interview with the user - map the decision tree, ask frontier questions in rounds with recommended answers, and settle every decision into a design brief. Use at Design intake for player-facing Petri work (before dispatching game-designer), or whenever the user wants a plan, decision, or idea stress-tested.
---

# Grilling

Interview the user relentlessly until you reach a shared understanding. Map the topic as a
**design tree**: every decision branches into the decisions that hang off it. The output is a
**design brief** - the settled tree, written down - which becomes the dispatch payload for the
`game-designer` agent (or, for a non-design topic, the agreed record of the decision).

This runs in the **main session only**. Subagents cannot talk to the user, so the orchestrator
owns the interview; the game-designer applies design expertise to the brief afterward.

## Ground yourself first

Before the first round, read what frames the design space so questions are sharp, not generic:

- `ROADMAP.md` - where the project currently is and what is queued around this work.
- Any backlog item, prior spec, or system the request touches.

## The protocol

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already
settled - the questions you can ask *now* without guessing at answers you haven't heard yet. Ask
the whole frontier in one round: number each question and give your recommended answer. Then wait
for the user's answers before the next round.

Format each question like so:

```
Q1 - <question title>: <question body, may be multiple paragraphs, including multiple choices>

-> Recommended: <your recommended answer and why>
```

When a round is small and the questions are choice-shaped, the `AskUserQuestion` tool is a fine
delivery mechanism (put the recommendation first, labeled "(Recommended)"); for open-ended or
many-question rounds, ask in chat with the format above.

Each round the user answers reshapes the tree - settled decisions push the frontier outward and
unblock questions that depended on them. Recompute the frontier and ask the next round. A
question whose answer depends on another question still open in this round belongs to a *later*
round, not this one.

**Finding facts is your job, never the user's.** When a frontier question needs a fact from the
environment (code, content TOML, docs, git history), look it up yourself or dispatch the built-in
`Explore` agent - do not ask the user for anything you could look up. Don't block on it: a
running exploration is an unsettled prerequisite, so only the questions downstream of it wait for
the agent to report - ask the rest of the frontier now.

**Decisions are the user's.** Put each one to them and wait. Do not silently assume an answer,
even the obvious one - the recommended answer exists so the user can confirm it in one word.

## Output: the design brief

The session is done when the frontier is empty: every branch of the design tree visited, nothing
left silently assumed. Then write the design brief covering:

- **Intent** - what the user actually wants and why (the root of the tree).
- **Settled decisions** - each decision, the chosen answer, and the reason, in tree order.
- **Rejected alternatives** - options considered and turned down, with the why (so the designer
  does not re-propose them).
- **Constraints confirmed** - determinism/data-driven/scope points the interview touched.
- **Deliberately deferred** - anything the user explicitly pushed out of scope.

Present the brief to the user for confirmation. Do not act on it until the user confirms the shared understanding.