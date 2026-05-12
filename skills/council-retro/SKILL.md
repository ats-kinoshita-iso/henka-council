---
name: council-retro
description: >
  Use this skill to run the per-cycle PDCA retrospective after a configurable
  number of sprints (default: every 5 sprints) complete, or when manually
  invoked by the user. Produces a structured Plan/Do/Check/Act output with the
  retrospective agent in pdca mode plus architect collaboration. MAY emit
  standard-work proposals via the nemawashi walkthrough — but MUST NOT write
  to standard-work.json directly.
version: "0.1.0"
tools:
  - Read
  - Glob
  - Grep
  - Write
  - Task
invocation: /henkaten-council:council-retro
---

# council-retro

Per-cycle PDCA retrospective skill for the henkaten-council governance plugin.
Invoked automatically by `/henkaten-council:council-autorun` Step 1I when the
sprint count reaches a cycle boundary (default: every N=5 sprints), or invoked
manually by the user at any time.

**Prerequisite:** `.council/` must already exist in the target project (run
`/henkaten-council:council-kickoff` first).

---

## Purpose and Cadence

`council-retro` is the full PDCA retrospective — the cadence where cross-sprint
patterns are analyzed systematically and standard-work proposals MAY be
generated (subject to evidence requirements and nemawashi approval).

| Attribute | Value |
|---|---|
| Cadence | Per-cycle (every N sprints; configurable in `.council/config.json`) OR manual |
| Trigger | council-autorun Step 1I (cycle boundary) OR user invocation |
| Mode | `pdca` (full PDCA analysis + architect collaboration) |
| Standard-work proposals | MAY produce proposals — ONLY via nemawashi walkthrough (Level 5 approval) |
| Output path | `.council/retrospectives/full-{date}.md` |
| Direct write to `standard-work.json` | **FORBIDDEN** — proposals MUST route via nemawashi |

---

## Mode: `pdca` — Plan / Do / Check / Act

This skill dispatches the Retrospective agent (see `agents/retrospective.md`)
in **`pdca` mode**, with Level 2 collaboration from the Architect agent
(`agents/architect.md`). The output is structured as four explicit sections:

### Plan

The **Plan** section captures what was intended for this cycle:
- What standard work was active during this cycle? (read `standard-work.json`)
- What improvement hypotheses were being tested? (read prior retrospectives)
- What cycle-level goals were set? (read `.harness/summary.md` if available)
- What constraints or dependencies were anticipated?

Link to relevant sprint contracts (`harness/sprints.json`, `.harness/contracts/sprint-{NN}.md`)
for the sprints covered by this cycle.

### Do

The **Do** section captures what was actually built and executed:
- Which sprints completed in this cycle, and what were their results (PASS / PARTIAL / FAIL)?
- Where did execution diverge from the Plan? What caused deviations?
- What decisions were made (read `.council/decision-log.jsonl`)?
- What Henkaten records were opened and/or closed (read `.council/henka-register.jsonl`)?

Link to commit history and evaluation reports for the sprints covered.

### Check

The **Check** section is the evidence-driven analysis:
- Cross-sprint patterns: what recurring issues, successes, or surprising behaviors
  appeared in ≥2 sprints? (Every pattern claim requires ≥2 sprint evidence.)
- Read `.harness/summary.md` for cross-sprint summary (if available).
- Read `regression.json` (or note its absence) for regression status.
- Read prior retrospectives (`.council/retrospectives/*.md`) for trend continuity.
- Read prior jishuken artifacts (`.council/jishuken/*.md`) as additional signal.
- What improvement hypotheses from the Plan were confirmed or refuted?
- What was the autonomy floor behavior? (read `.council/state/effective-autonomy.json`)

### Act

The **Act** section surfaces process improvement candidates:
- What standard-work changes are candidates based on the Check findings?
- Each proposal must be grounded in ≥2 sprints of evidence (or 1 sprint with
  strong deterministic evidence and explicit justification).
- Proposals are listed here as candidates — NOT applied directly.
- Each candidate proposal that the team wants to advance MUST be routed through
  the nemawashi walkthrough (Step 1D of council-autorun) for Level 5 approval.
- **The Retrospective agent MUST NOT write to `standard-work.json` directly.**
  All standard-work changes require the four-stage nemawashi walkthrough and
  explicit user approval (Level 5) before any modification.

---

## Step P0 — Load Cycle Context

Read:
- `.harness/sprints.json` — full sprint list; identify cycle boundary
- `.harness/sprint-state.json` — current sprint number and result
- `.council/config.json` — cycle length (`cycle_length`, default 5)
- `.council/state/effective-autonomy.json` — autonomy floor state
- `.harness/summary.md` — cross-sprint summary (if present; note absence if not)
- `regression.json` — regression status (if present; note absence if not)
- `.council/henka-register.jsonl` — open and recently closed Henkaten records
- `.council/decision-log.jsonl` — decisions made during this cycle
- `.council/standard-work.json` — current standard-work baseline
- All `.council/retrospectives/sprint-{NN}-mini.md` for sprints in this cycle
- All `.council/jishuken/*.md` artifacts created during this cycle

---

## Step P1 — Agent Fan-Out (pdca mode + architect)

Dispatch two agents as fork-context subagents via `Task`:

1. **`agents/retrospective.md`** in `pdca` mode — primary analysis agent.
   Produces the draft PDCA output: Plan, Do, Check, Act sections.

2. **`agents/architect.md`** (Level 2 collaboration) — structural review of
   the retrospective draft. Checks that: Plan section links to sprint contracts,
   Do section cites actual commit evidence, Check patterns have ≥2 sprint
   backing, Act proposals are grounded in evidence.

**Sequential dispatch (Q6 default).** Architect reviews the retrospective
agent's draft output before the final file is assembled.

Both agents are read-only and proposal-only (Level 2). Neither may write to
any file. The Orchestrator assembles the final output from their proposals.

---

## Step P2 — Assemble and Write PDCA Output

The Orchestrator assembles the final output from the two agents' proposals and
writes to:

```
.council/retrospectives/full-{date}.md
```

Where `{date}` is the UTC date in `YYYY-MM-DD` format.

Use `templates/retrospective-pdca.md` as the scaffold. The output file MUST
contain all four explicit PDCA section headings: `## Plan`, `## Do`,
`## Check`, `## Act`.

---

## Step P3 — Standard-Work Proposal Routing

If the Act section contains candidates for standard-work changes:

1. Surface each candidate to the user as a proposed change.
2. For each candidate the user wants to advance: initiate the nemawashi
   walkthrough (per council-autorun Step 1D), which routes through the
   four-stage process (Stage 1: position paper → Stage 2: per-agent
   presentation → Stage 3: alignment → Stage 4: ratify).
3. Write a DEC entry via `scripts/append-decision.py` for each proposal
   (whether ratified or deferred).
4. The actual write to `standard-work.json` occurs ONLY after explicit Level 5
   (user) ratification at Stage 4 of the nemawashi walkthrough.
5. Proposals that are NOT advanced are noted in the PDCA file's Act section
   for the next cycle's Plan reference.

**The council-retro skill does NOT write to `standard-work.json` directly.**
Standard-work changes require the full nemawashi walkthrough via council-autorun
Step 1D. This constraint is enforced by the nemawashi walkthrough itself.

---

## Yokoten Propagation

When the PDCA retrospective closes (resolves) a Henkaten record, the
Retrospective agent populates the `yokoten` block:

```yaml
yokoten:
  applicable_to_subsequent_sprints: [NN+1, NN+2]   # or ["all"]
  adaptation_notes: >
    {Starting point for the adaptation prompt at the next cycle boundary.}
```

Fields:
- `applicable_to_subsequent_sprints` — list of future sprint numbers (or
  `["all"]`) that receive this learning as a Step 1A.5 adaptation prompt
- `adaptation_notes` — human-readable starting point for the adaptation

The ratify-once shortcut (v2.1 A9) applies when the value is `["all"]` or
contains ≥3 sprint numbers.

---

## What This Skill Does NOT Do

- **Does NOT write to `standard-work.json` directly** — all standard-work
  changes require nemawashi walkthrough (see Step P3)
- **Does NOT run per-sprint mini retrospectives** — those are council-retro-mini
  (Step 1H), running after every sprint
- **Does NOT delegate to trine-eval** — that is council-autorun's Step 1B
- **Does NOT replace council-retro-mini** — the mini skill runs per-sprint;
  this skill runs per-cycle and is more comprehensive

---

## Cross-References

| Dependency | Purpose |
|---|---|
| `agents/retrospective.md` | Retrospective agent dispatched in `pdca` mode |
| `agents/architect.md` | Level 2 structural review of the PDCA draft |
| `templates/retrospective-pdca.md` | Scaffold for the output `.council/retrospectives/full-{date}.md` file |
| `skills/council-autorun/SKILL.md` Step 1D | Nemawashi walkthrough for routing Act section proposals (standard-work changes) |
| `skills/council-autorun/SKILL.md` Step 1I | Caller of this skill at cycle boundaries |
| `skills/council-retro-mini/SKILL.md` | Per-sprint mini retrospective (source of Learning Points aggregated here) |
| `.harness/summary.md` | Cross-sprint summary read as primary input for Check section |
| `regression.json` | Regression status read as secondary input for Check section |
| `scripts/append-decision.py` | DEC entry emission for nemawashi proposal routing |
| `scripts/append-henka.py` | Yokoten block updates when closing Henkaten records |
