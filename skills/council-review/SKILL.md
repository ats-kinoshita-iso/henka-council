---
name: council-review
description: >
  Use this skill to manually run the council fan-out (architect,
  scope-guardian, henkaten-detector, retrospective) for an ad-hoc review, or
  to restore the autonomy floor via --restore-autonomy after a halt. Invoked
  by the user as `/henkaten-council:council-review` at any point outside the
  per-sprint autorun loop — especially after a sprint halt, an andon stop, or
  whenever human-in-the-loop review is required. Carries identical andon and
  verification spot-check protocols to council-autorun.
version: "0.1.0"
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Task
invocation: /henkaten-council:council-review
flags:
  - name: "--restore-autonomy"
    description: >
      Reset the dynamic autonomy floor to a higher level after the user has
      reviewed and resolved the conditions that triggered the floor drop. This
      is the SINGLE canonical path to restore the autonomy floor (v2.1
      amendment A5). Requires Level 5 (human-approved) authority — the user
      explicitly invokes this flag; the orchestrator never auto-triggers it.
---

# council-review

Manual-trigger governance review skill for the henkaten-council plugin. This
is the **sibling** of `skills/council-autorun/SKILL.md` — same council agents,
same andon and verification protocols, but invoked by the user rather than
automatically by the per-sprint loop.

**Prerequisite:** `.council/` must already exist in the target project (run
`/henkaten-council:council-kickoff` first).

---

## Purpose

`council-review` and `council-autorun` are **sibling flows**, not parent/child.
Neither invokes the other.

| Skill | Trigger | Scope | trine-eval delegation |
|---|---|---|---|
| `council-autorun` | Automatic, per-sprint; called by `/trine-eval:harness-sprint` | Full 1A → 1I sequence | Yes — delegates to `/trine-eval:harness-sprint` in Step 1B |
| `council-review` | Manual, user-invoked; at any time | Fan-out + verification spot-check + decision-log entry | **No** — never delegates to trine-eval |

Use `council-review` when:
- The orchestrator has halted (andon stop, autonomy floor breach, blocking Henkaten) and you want a fresh council look at current state
- You want to review course-corrections outside the autorun loop
- You are invoking `--restore-autonomy` to restore an autonomy floor that was dropped by halt conditions

`council-review` runs a **subset** of the autorun sequence: fan-out, andon handling, verification spot-check, and decision-log entry. It does NOT run the full Step 1A through 1I autorun sequence.

---

## Step R0 — Load State

Read `.harness/sprints.json`, `.harness/config.json`, `.council/config.json`,
and `.council/state/effective-autonomy.json`. Determine the current sprint
context and effective autonomy level.

If `--restore-autonomy` is present in the invocation, jump directly to
[Step R4 — Restore Autonomy Floor](#step-r4--restore-autonomy-floor).

Otherwise continue to Step R1.

---

## Step R1 — Manual Fan-Out

*Mirrors autorun Step 1C. Applies the same sequential-default / parallel-swarm
dispatch model (v2.1 Q6 and A6).*

### R1.1 — Fan-Out (Sequential Default)

Per **Q6 default**: dispatch agents **sequentially** unless `dispatch_mode:
parallel` is set in `.council/config.json`.

Agent dispatch order:

1. `agents/architect.md` — structural / contract alignment review
2. `agents/scope-guardian.md` — scope drift detection
3. `agents/henkaten-detector.md` — change-point classification
4. `agents/retrospective.md` — in `mini` mode (observations only)

Each agent is dispatched as an isolated subagent via `Task`, using the
`templates/dispatch-envelope.md` envelope. Pass only file paths and structured
constraints — never pass orchestrator reasoning into the subagent context.

**Andon-Swarm Dispatch is unconditionally parallel (v2.1 A6):** when an andon
signal triggers a swarm, swarm agents are dispatched via parallel `Task` calls
regardless of `dispatch_mode` setting.

### R1.2 — Fan-In and Evidence Check

Each agent output is accepted only if it includes:
- `evidence_class` (one of `observed`, `inferred`, `speculative`)
- `confidence` (integer 1–5)
- `coverage` (list of files/paths examined vs. unavailable)
- For `observed` claims: a `verification` field with a re-runnable command

Agent outputs that returned `status: error` are logged and skipped.

### R1.3 — Andon Handling

Every agent output is scanned for an `andon_signal` field. The orchestrator
MUST refer to `instructions/andon-protocol.md` for full protocol semantics,
pull-rate tracking, and the distinct-originator corroboration rule.

**On `andon_signal: stop`:**

1. Write the thank-the-puller acknowledgment **verbatim and immediately**,
   before any analysis. Per `instructions/andon-protocol.md`:
   > "Thank you for stopping the line. Your signal has been received and will
   > be honored. No further sprint steps will proceed until this is resolved."
2. Halt the review immediately. Skip all remaining agents in the fan-out.
3. Jump to Step R3 (decision-log entry for the halt).

**On `andon_signal: alert`:**

1. Write the thank-the-puller acknowledgment verbatim.
2. Pause the review.
3. Dispatch the **swarm** (parallel `Task` calls, unconditionally per A6):
   - Originating agent + any agents named in `swarm_request`
   - Total capped at 4 agents
   - Resolution window: `andon_takt_seconds` from `.council/config.json`
     (default: 600 seconds / 10 minutes)
4. If swarm resolves within the takt bound → review resumes. Log a DEC entry
   with `andon_resolution`.
5. If swarm does NOT resolve within the takt bound → escalates to `stop`.
   Jump to Step R3.

### R1.4 — Verification Spot-Check

For every agent output, identify all claims with `evidence_class: "observed"`.
From those claims, **randomly sample one** and re-run its `verification`
command via:

```
python scripts/run-verification.py "<verification_string>"
```

`scripts/run-verification.py` enforces the §7.0.2 syntax allowlist (read-only
git/grep/cat/jq/test/validation helpers) with a 10-second execution timeout
and project-root CWD.

**If the verification string is NOT on the allowlist (pre-execution check):**

1. Reject the agent's claim.
2. Log an `agent-capability-change` Henkaten record via `scripts/append-henka.py`:
   ```json
   {
     "fourM_axis": "Machine",
     "change_origin": "active",
     "change_type": "agent-capability-change",
     "description": "Non-conformant verification string rejected in council-review",
     "rejected_string": "<the offending string>",
     "agent_id": "<agent>"
   }
   ```
3. Flag the agent output as partially unverified. Do not apply any corrections
   derived from the unverified claim.
4. Ask the agent to resubmit with a conformant `verification` string.

**If the verification command runs but the result diverges from the agent's
report:** log a `quality-defect-anomaly` Henkaten record with
`change_origin: passive` and high impact.

Log all spot-check results (pass or fail) to `audit-log.jsonl`.

---

## Step R2 — Present Findings and Course Corrections

After fan-in, present the consolidated agent findings to the user.

For any proposed course corrections surfaced by the agents:

- **Minor reversible corrections:** may be auto-applied after a single prompt:
  *"Apply minor correction X? (yes/no)"*
- **Major corrections or any irreversible action:** surface the position paper
  template and request user decision. The formal nemawashi walkthrough for major
  corrections follows the four-stage process documented in
  `skills/council-autorun/SKILL.md` Step 1D — council-review can SURFACE
  conflicts and initiate the walkthrough, but the canonical walkthrough
  machinery lives in council-autorun's Step 1D documentation.

---

## Step R3 — Decision-Log Entry

For each action taken (correction applied, halt recorded, andon resolution),
append a `DEC` entry to `.council/decision-log.jsonl` via
`scripts/append-decision.py`.

Required fields follow `schemas/decision-log-entry.schema.json`. For a
council-review session, key fields include:

| Field | Typical value |
|---|---|
| `decision_id` | `DEC-{NNNN}` (sequential) |
| `decision_type` | `"council-review-correction"`, `"sprint-halt"`, `"andon-resolution"` |
| `decision_outcome` | `"applied"`, `"proposed"`, `"halted"` |
| `autonomy_level_used` | Effective level at the time of the decision |
| `effective_autonomy_at_decision` | Level from `.council/state/effective-autonomy.json` |
| `reversibility` | `"reversible"` or `"irreversible"` |
| `nemawashi_walkthrough_version` | `null` for minor reversible auto-applied changes |
| `description` | Human-readable summary of what was decided and why |

---

## Step R4 — Restore Autonomy Floor (`--restore-autonomy`)

*v2.1 amendment A5 — the SINGLE canonical floor-reset path.*

The `--restore-autonomy` flag is the **only canonical path** to raise the
autonomy floor. No other skill, agent, command, or automated code path may
reset the floor. Any other code path that attempts to raise the level is a bug
per v2.1 amendment A5.

**Authority level: Level 5 (human-approved).** The user explicitly invokes
`/henkaten-council:council-review --restore-autonomy`. The orchestrator does
not auto-trigger this flag under any conditions.

### R4.1 — Confirm Current Floor State

Read `.council/state/effective-autonomy.json`. Surface:
- The current (lower) autonomy level
- The `trigger_history` array showing what caused the floor drop
- A summary of the conditions that led to the drop (andon stops, consecutive
  FAILs, high-risk active Henkaten records)

Prompt the user:
> "The current autonomy floor is Level {N} (dropped from Level {M} due to:
> {trigger_reason}). Please confirm the level you wish to restore to: (1/2/3/4)"

### R4.2 — Write DEC Entry

Before updating the state, emit a DEC entry via `scripts/append-decision.py`
with the following fields:

```yaml
decision_id: DEC-{NNNN}        # sequential, ^DEC-[0-9]{4,}$ format
decision_type: autonomy-floor-restore
decision_outcome: applied       # the new (higher) level as the outcome
autonomy_level_used: 5          # Level 5: human-approved invocation
effective_autonomy_at_decision: {new_level}   # the restored (higher) level
previous_level: {old_level}     # the level before restore
reversibility: reversible       # the floor can be re-lowered by halt conditions
nemawashi_walkthrough_version: null   # restore is a Level-5 single-prompt action
status: ratified
applied_at: <ISO-8601 UTC timestamp>
trigger: "--restore-autonomy invoked by user via /council-review"
description: >
  Autonomy floor restored from Level {old_level} to Level {new_level}.
  Trigger conditions resolved: {e.g., "two consecutive sprint FAILs resolved",
  "andon-stop swarm complete", "blocking Henkaten closed"}.
```

Note on `reversibility`: `reversible` here means the floor can be re-lowered
if new halt conditions arise. However, the restore action itself requires
deliberate human re-invocation to undo — it is not silently undone by
automated processes.

### R4.3 — Persist New Floor State

After the DEC entry is written, invoke `scripts/update-effective-autonomy.py`
with the new level and trigger evidence:

```
python scripts/update-effective-autonomy.py \
  --level {new_level} \
  --trigger "restore-autonomy: DEC-{NNNN}" \
  --evidence "User invoked --restore-autonomy after resolving: {conditions}"
```

This writes the updated state to `.council/state/effective-autonomy.json`.

### R4.4 — Confirm Restoration

Surface a confirmation to the user:

> "Autonomy floor restored to Level {new_level}. DEC-{NNNN} logged.
> `.council/state/effective-autonomy.json` updated. The sprint loop may now
> resume by invoking the council-autorun skill."

---

## What council-review Does NOT Do

Explicit out-of-scope for this skill:

- **Does NOT delegate to `/trine-eval:harness-sprint`** — that is autorun's
  exclusive Step 1B. council-review never touches trine-eval.
- **Does NOT run the full 1A → 1I autorun sequence** — council-review runs a
  subset: fan-out + verification spot-check + decision-log entry only.
- **Does NOT trigger context compaction or per-sprint mini-retro** — those are
  Steps 1G and 1H in autorun; they only fire in the per-sprint loop.
- **Does NOT initiate a nemawashi walkthrough on its own** — council-review
  can SURFACE conflicts and propose a walkthrough, but the formal four-stage
  walkthrough machinery (Stages 1–4: position paper → sequential presentation
  → alignment revision → ratification) is documented in
  `skills/council-autorun/SKILL.md` Step 1D. council-review defers to
  council-autorun's walkthrough documentation.
- **Does NOT invoke council-autorun** — these are sibling skills. council-review
  does not delegate to or call council-autorun as a sub-skill or parent/child
  relationship. They share the same agents and protocols but are independent flows.

---

## Cross-References

| Dependency | Purpose |
|---|---|
| `instructions/andon-protocol.md` | Full andon protocol: thank-the-puller acknowledgment, Rule 4 carve-out, pull-rate tracking, distinct-originator corroboration rule |
| `scripts/run-verification.py` | §7.0.2 allowlist enforcement for verification spot-check (Step R1.4) |
| `scripts/append-henka.py` | Append-only writer for `.council/henka-register.jsonl` |
| `scripts/append-decision.py` | DEC entry emission to `.council/decision-log.jsonl` (Step R3, R4.2) |
| `scripts/update-effective-autonomy.py` | Persists restored floor to `.council/state/effective-autonomy.json` (Step R4.3) |
| `skills/council-autorun/SKILL.md` | Per-sprint sibling flow; canonical four-stage nemawashi walkthrough in Step 1D |
| `agents/architect.md` | Structural review agent (L2, fork context) |
| `agents/scope-guardian.md` | Scope drift detection agent (L2, fork context) |
| `agents/henkaten-detector.md` | Change-point classification agent (L1, fork context) |
| `agents/retrospective.md` | Retrospective agent (L2, mini mode) |
| `schemas/decision-log-entry.schema.json` | Schema for DEC entries (Steps R3, R4) |
| `templates/dispatch-envelope.md` | Standardized subagent dispatch template (Step R1.1) |
