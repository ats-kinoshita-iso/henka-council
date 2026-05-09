---
name: council-retro-mini
description: >
  Use this skill to run the per-sprint mini retrospective automatically after
  every sprint completes. Invoked by council-autorun at Step 1H; runs in ≤30s
  wall-clock time with no user input required. Capture-only: produces Learning
  Points and Pattern Observations. No standard-work proposals are permitted in
  mini mode.
version: "0.1.0"
tools:
  - Read
  - Glob
  - Grep
  - Write
invocation: /henkaten-council:council-retro-mini
---

# council-retro-mini

Per-sprint mini retrospective skill for the henkaten-council governance plugin.
Runs automatically inline at Step 1H of `/henkaten-council:council-autorun`
after every sprint evaluation completes. This skill is the full implementation
of the Step 1H stub that shipped in sprint 6.

**Prerequisite:** `.council/` must already exist in the target project (run
`/henkaten-council:council-kickoff` first).

---

## Purpose and Cadence

`council-retro-mini` provides a lightweight, immediate retrospective capture
after every sprint. The goal is to capture learning while context is fresh —
NOT to prescribe process changes. Standard-work proposals belong to the `pdca`
mode (`/henkaten-council:council-retro`) and must not appear here.

| Attribute | Value |
|---|---|
| Cadence | Per-sprint, automatic |
| Trigger | Step 1H of council-autorun (after every sprint result) |
| Mode | `mini` (capture-only) |
| Time budget | **≤30s wall-clock** |
| User input required | No — fully automatic |
| Standard-work proposals | **NO. This mode MUST NOT include any standard-work proposals.** |
| Output path | `.council/retrospectives/sprint-{NN}-mini.md` |

---

## Time Budget

**This skill must complete within 30s (30 seconds wall-clock).** If evidence
gathering is incomplete within the time budget, note it in the `coverage` field
and defer analysis to the next `pdca` cycle. Do not exceed the time limit by
attempting comprehensive analysis — concise and timely beats thorough and slow.

---

## Mode: `mini` — Capture-Only

This skill dispatches the Retrospective agent (see `agents/retrospective.md`)
in **`mini` mode**. The `mini` mode contract is:

- **Learning Points** — what worked, what was harder than expected, what
  surprised the team (sprint scope only, not cross-sprint synthesis)
- **Pattern Observations** — early signals of recurring patterns; note that
  ≥2 sprints are needed to confirm a pattern — label as `inferred`, not
  `observed`

**No standard-work proposals in mini mode.** This is a capture-only cadence.
The Retrospective agent MUST NOT include proposals, kaizen recommendations, or
process-change suggestions in `mini` mode output. Observations that suggest a
process change are noted in Learning Points as observations only; the proposal
is deferred to the next `pdca` cycle.

---

## Step M0 — Load Sprint Context

Read:
- `.harness/sprint-state.json` — sprint number and result (PASS / PARTIAL / FAIL)
- `.harness/contracts/sprint-{NN}.md` — scope and success criteria for this sprint
- `.harness/evals/sprint-{NN}-r{R}.md` (most recent) — evaluator verdict and evidence

These reads must complete within the 30s budget. If a file is unavailable, note
it in `coverage` and continue with partial data.

---

## Step M1 — Dispatch Retrospective Agent (mini mode)

Dispatch `agents/retrospective.md` as a fork-context subagent via `Task` in
**`mini` mode**. Pass:
- Sprint number
- Sprint result
- Path to the most recent eval report
- File paths read in Step M0

**Time cap:** the subagent's output must return within the remaining time budget
(≤25s is the target — 5s overhead for Step M2 write). If the subagent exceeds
the budget, interrupt and use whatever partial output was returned.

The subagent is capture-only: standard-work proposals are forbidden in mini
mode. If the subagent output contains any proposal for standard-work changes,
classify it as a constraint violation and strip the offending section before
writing the output file.

---

## Step M2 — Write Mini Retrospective File

The Orchestrator (not the subagent) writes the output file to:

```
.council/retrospectives/sprint-{NN}-mini.md
```

Use `templates/retrospective-mini.md` as the scaffold.

### Required File Contents

1. **Sprint metadata** — sprint number, title (from contract), date (UTC ISO
   8601), result (PASS / PARTIAL / FAIL)
2. **Learning Points** — concise bulleted list (3–7 items max to fit the time
   budget)
3. **Pattern Observations** — early signal notes; labeled `inferred` if based
   on fewer than 2 sprints
4. **Henkaten records closed this sprint** — list of HK-NNNN records resolved
   in this sprint's scope (read from `.council/henka-register.jsonl`)
5. **Yokoten block** — populated for each closed Henkaten record (see Yokoten
   section below)

---

## Yokoten Propagation

When the mini retrospective closes (resolves) a Henkaten record, the
Retrospective agent populates the `yokoten` block of that record:

```yaml
yokoten:
  applicable_to_subsequent_sprints: [NN+1, NN+2]   # or ["all"] for universal lessons
  adaptation_notes: >
    {Brief starting point for the adaptation — what the next sprint should
    be aware of or do differently based on this resolved issue.}
```

**`applicable_to_subsequent_sprints`** — list of future sprint numbers that
should receive this learning as an adaptation prompt. Use `["all"]` for
universal lessons. The ratify-once shortcut (v2.1 A9) applies when the value
is `["all"]` or contains ≥3 sprint numbers.

**`adaptation_notes`** — the human-readable starting point for the
adaptation. The user (not the agent) drafts the actual adaptation text during
Step 1A.5 of subsequent sprints. The agent provides a concise starting point
only.

Council-autorun Step 1A.5 (Yokoten Review) reads all `henka-register.jsonl`
records with a populated `yokoten` block and surfaces adaptation prompts at the
start of subsequent sprints. The `council-retro-mini` skill is the primary
writer of yokoten blocks for per-sprint Henkaten closures.

---

## What This Skill Does NOT Do

- **No standard-work proposals in mini mode.** The capture-only rule is
  absolute. Any finding that suggests a process change is recorded as an
  observation for the next `pdca` cycle — not as a proposal here.
- **Does NOT invoke the nemawashi walkthrough.** Standard-work changes require
  the PDCA cycle via `/henkaten-council:council-retro` and Level 5 approval.
- **Does NOT perform cross-sprint trend synthesis.** That belongs to `pdca` mode.
- **Does NOT require user input.** Runs inline and automatically.
- **Does NOT persist session context.** Context compaction (Step 1G) runs
  separately in council-autorun.

---

## Cross-References

| Dependency | Purpose |
|---|---|
| `agents/retrospective.md` | Retrospective agent dispatched in `mini` mode |
| `templates/retrospective-mini.md` | Scaffold for the output `.council/retrospectives/sprint-{NN}-mini.md` file |
| `skills/council-autorun/SKILL.md` Step 1H | Caller of this skill; defines the per-sprint stub behavior this skill replaces |
| `skills/council-autorun/SKILL.md` Step 1A.5 | Yokoten review step that reads the yokoten blocks written here |
| `skills/council-retro/SKILL.md` | PDCA retrospective — the cadence where standard-work proposals ARE permitted |
| `.council/henka-register.jsonl` | Source for closed Henkaten records and destination for yokoten block writes (via `scripts/append-henka.py`) |
| `scripts/append-henka.py` | Append-only writer used to update yokoten blocks in `henka-register.jsonl` |

---

## Output Contract

The output file `sprint-{NN}-mini.md` is a governance artifact. It:
- Is written once per sprint (idempotent: if the file already exists for sprint
  NN, log a warning and skip — do not overwrite without explicit user approval)
- Is NOT append-only (it is a single file, not a `.jsonl` log)
- May be reviewed by the user after the sprint without any action required
- Does NOT block the next sprint — the autorun loop proceeds to Step 1I
  immediately after this file is written
