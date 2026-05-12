---
name: council-jishuken
description: >
  Use this skill to run an on-demand, user-invoked reflection workshop on a
  chosen topic. Operates in jishuken mode: produces Reflection Notes, Open
  Questions, and Hypotheses. This is a reflection-only skill — it does NOT
  produce standard-work proposals and does NOT propose changes to
  standard-work.json. Floor restoration is exclusively handled by
  council-review --restore-autonomy, not by this skill.
version: "0.1.0"
tools:
  - Read
  - Glob
  - Grep
  - Write
  - Task
invocation: /henkaten-council:council-jishuken [topic]
---

# council-jishuken

Per-period user-invoked reflection workshop skill for the henkaten-council
governance plugin. Completely decoupled from sprint boundaries and from
standard-work proposals (per §8.6 and Q16). Jishuken (自主研) is an autonomous
deep-study session: participants step back from day-to-day execution to
investigate a specific topic through structured reflection.

**Prerequisite:** `.council/` must already exist in the target project (run
`/henkaten-council:council-kickoff` first).

---

## Purpose and Cadence

`council-jishuken` is a free-form, user-directed reflection tool. The user
picks the topic and timing — it is not constrained by sprint boundaries or
cycle counts. It is entirely separate from the automatic retrospective cadences
(`council-retro-mini` per-sprint and `council-retro` per-cycle).

| Attribute | Value |
|---|---|
| Cadence | Per-period, manual user invocation |
| Trigger | User runs `/henkaten-council:council-jishuken [topic]` |
| Mode | `jishuken` (reflection-only) |
| Standard-work proposals | **NO. This skill is reflection-only and MUST NOT produce standard-work proposals.** |
| Output path | `.council/jishuken/<topic>-<date>.md` |
| Autonomy floor reset | **NOT available here. Use `/council-review --restore-autonomy` for floor restoration.** |

---

## Reflection-Only Constraint

**This skill is reflection-only.** It does not propose standard-work changes,
does not invoke the nemawashi walkthrough, and does not produce kaizen
recommendations. The output is analytical, not prescriptive.

Jishuken is decoupled from standard-work changes (Q16). A jishuken finding
that suggests a standard-work change must be re-raised in a future PDCA pass
via `/henkaten-council:council-retro`. The user decides when and whether to
make that transition. The jishuken skill does not initiate or describe that
transition as an action.

---

## Invocation

```
/henkaten-council:council-jishuken [topic]
```

The `[topic]` argument is required. It becomes part of the output filename:
`.council/jishuken/<topic>-<date>.md`. Topics should be concise identifiers,
e.g.:
- `autonomy-floor-volatility`
- `sprint-5-to-8-patterns`
- `architect-coverage-gaps`
- `andon-signal-calibration`

If no topic is provided, the Orchestrator prompts the user to supply one before
proceeding.

---

## Mode: `jishuken` — Structured Reflection

This skill dispatches the Retrospective agent (see `agents/retrospective.md`)
in **`jishuken` mode**, with Level 2 collaboration from the Architect agent
(`agents/architect.md`). The output is structured around three reflection
sections:

### Reflection Notes

Observations, historical context, and evidence about the chosen topic:
- What does the record show? (eval reports, decision logs, Henkaten records,
  mini retrospectives, prior PDCA cycles)
- What patterns or anomalies are visible in the evidence?
- What has changed over time on this topic?

### Open Questions

Questions raised by the evidence that cannot yet be answered:
- What remains unclear or ambiguous?
- What additional evidence would resolve the ambiguity?
- What assumptions are embedded in the current standard work on this topic?
- What would need to be true for the pattern to be benign? Problematic?

### Hypotheses

Tentative theories about underlying dynamics:
- What are the candidate causal explanations for the observed patterns?
- How could each hypothesis be tested in a future sprint or PDCA cycle?
- Which hypotheses are most actionable if confirmed?

**Note:** Hypotheses generated here are candidates for future `pdca` cycle
investigation, not immediate action items. The mechanism for converting a
hypothesis into a standard-work change is the PDCA retrospective
(`/council-retro`), not this skill.

---

## Step J0 — Load Topic Context

The Orchestrator loads relevant evidence files for the specified topic:
- `.council/henka-register.jsonl` — Henkaten records matching the topic
- `.council/decision-log.jsonl` — decisions related to the topic
- `.harness/evals/sprint-{NN}-r{R}.md` — evaluation reports (all available)
- `.council/retrospectives/sprint-{NN}-mini.md` — mini retrospectives
- `.council/retrospectives/full-{date}.md` — PDCA retrospectives (if any)
- `.council/jishuken/*.md` — prior jishuken artifacts (for continuity)
- `.council/standard-work.json` — current standard-work baseline (read-only)
- `.council/state/effective-autonomy.json` — autonomy floor history

Topic relevance is determined heuristically — the Orchestrator selects files
most likely to contain signal for the user-specified topic.

---

## Step J1 — Agent Fan-Out (jishuken mode + architect)

Dispatch two agents as fork-context subagents via `Task`:

1. **`agents/retrospective.md`** in `jishuken` mode — primary reflection agent.
   Produces the three-section output: Reflection Notes, Open Questions,
   Hypotheses.

2. **`agents/architect.md`** (Level 2 collaboration) — structural review.
   Checks that: Reflection Notes are evidence-grounded, Open Questions are
   genuinely open (not rhetorical), Hypotheses are falsifiable and linked to
   the evidence.

**Sequential dispatch (Q6 default).** Both agents are read-only and
proposal-only. Neither writes any file. The Orchestrator assembles the output.

---

## Step J2 — Write Jishuken Output

The Orchestrator writes the output file to:

```
.council/jishuken/<topic>-<date>.md
```

Where `<topic>` is the normalized topic argument (lowercase, hyphens for
spaces) and `<date>` is the UTC date in `YYYY-MM-DD` format.

Use `templates/jishuken-workshop.md` as the scaffold. The output file must
contain all three section headings: `## Reflection Notes`, `## Open Questions`,
`## Hypotheses`.

---

## Autonomy Floor

The autonomy floor (`/council-review --restore-autonomy`) is a separate
concern handled exclusively by the `council-review` skill. This skill does
not interact with the autonomy floor, does not surface floor-reset prompts,
and does not provide any path to modify the effective autonomy level. If the
user needs to restore the autonomy floor after a halt, they must invoke:

```
/henkaten-council:council-review --restore-autonomy
```

That is the single canonical path (v2.1 amendment A5). No other skill,
including this one, provides an alternative path to floor restoration.

---

## What This Skill Does NOT Do

- **Does NOT produce standard-work proposals.** Reflection-only. No proposals,
  no nemawashi walkthrough invocation, no kaizen recommendations. Any finding
  that suggests a standard-work change must be re-raised by the user in a future
  PDCA pass (`/council-retro`).
- **Does NOT initiate nemawashi.** The nemawashi walkthrough is the path for
  standard-work changes; jishuken does not trigger or describe that flow as an
  output action.
- **Does NOT provide an autonomy floor reset path.** Floor restoration is
  exclusively `/council-review --restore-autonomy` (A5). This skill does not
  reference or implement any alternative floor-reset mechanism.
- **Does NOT run automatically.** This skill is always user-invoked with an
  explicit topic. It does not run as part of the council-autorun loop.
- **Does NOT close Henkaten records.** Jishuken is observational. Formal
  Henkaten record closure happens during mini (`council-retro-mini`) or PDCA
  (`council-retro`) retrospectives.

---

## Cross-References

| Dependency | Purpose |
|---|---|
| `agents/retrospective.md` | Retrospective agent dispatched in `jishuken` mode |
| `agents/architect.md` | Level 2 structural review of the reflection draft |
| `templates/jishuken-workshop.md` | Scaffold for the output `.council/jishuken/<topic>-<date>.md` file |
| `skills/council-review/SKILL.md` | The `--restore-autonomy` flag is the canonical autonomy floor reset path — NOT this skill |
| `skills/council-retro/SKILL.md` | The PDCA pass where jishuken hypotheses can be converted to standard-work proposals if the user chooses to advance them |
| `.council/henka-register.jsonl` | Henkaten records read as evidence for the reflection topic |
| `.council/jishuken/` | Output directory for this skill's artifacts |
