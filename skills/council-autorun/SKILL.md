---
name: council-autorun
description: >
  Use this skill to run the council fan-out sequence (henkaten check, agent
  fan-out, decision logging, retrospective) for the next harness sprint, after
  the user runs `/trine-eval:harness-sprint`. Invoked as the
  `council-autorun` slash command under the `henkaten-council` plugin. Runs the
  full ten-step governance loop defined in §8.2 of the Phase-0 v2 proposal:
  pre-sprint henkaten check, yokoten review, trine-eval delegation, council
  fan-out, course correction, decision logging, halt condition evaluation,
  context compaction, mini retrospective, and next-sprint trigger logic.
version: "0.1.0"
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Task
invocation: /henkaten-council:council-autorun
---

# council-autorun

Outer sprint-loop skill for the henkaten-council governance plugin. Wraps
`/trine-eval:harness-sprint` with pre-sprint change-point detection, post-sprint
council review, course correction, dynamic autonomy floor management, context
compaction, and retrospective capture.

**Prerequisite:** `.council/` must already exist in the target project (run
`/henkaten-council:council-kickoff` first). If `.council/` is absent, this
skill halts at Step 0 and instructs the user to run `council-kickoff`.

**Step 0 — Load State.**
Read `.harness/sprints.json`, `.harness/config.json`,
`.council/config.json`, and `.council/state/effective-autonomy.json`. Determine
the current sprint number and effective autonomy level. If `.council/` is
missing, halt and instruct the user to run `/henkaten-council:council-kickoff`
first.

---

## Step 1A — Pre-Sprint Henkaten Check

*Source: §8.2 Step 1A, v2.1 amendment A3*

**Purpose:** detect and classify any change-points before handing off to
trine-eval. If high-risk or blocking changes are found, halt before any sprint
work begins.

**When `.council/` does not exist:** this step is a NO-OP — the autorun
continues to Step 1A.5. The kickoff check in Step 0 will have already caught
this case; the NO-OP rule applies when `.council/` is present but empty.

### 1A.1 — Plugin Manifest Diff

Compare the current `.claude-plugin/plugin.json` against the version recorded
in the last sprint's baseline (or the last git-committed version, whichever is
more recent):

```
git diff HEAD -- .claude-plugin/plugin.json
```

Any diff triggers an `agent-capability-change` Henkaten record via
`scripts/append-henka.py`.

### 1A.2 — Unresolved Henkaten Record Check

Read `.council/henka-register.jsonl`. A record is **unresolved** if its
`resolution_status` field is anything other than `"resolved"` (equivalently: if
it lacks a `closed_at` timestamp). Surface all unresolved records to the
orchestrator's working context.

- **Blocking or high-risk unresolved records** → issue `andon_signal: stop`;
  jump to Step 1F.
- **Actionable or informational unresolved records** → attach as context notes;
  proceed.
- **No unresolved records** → proceed normally.

### 1A.3 — Change-Origin Classification (R1)

For every newly detected change-point (manifest diff, state drift, user-modified
files outside governance):

- `change_origin: active` — the council or orchestrator initiated the change
  (e.g., a previously-applied course correction).
- `change_origin: passive` — the change arrived from outside (user edit, CI
  artifact, trine-eval output, external dependency bump).

Classify on the 4M axis (Man / Machine / Method / Material) per the
`schemas/henka-record.schema.json` `fourM_axis` enum. Log via
`scripts/append-henka.py`.

### 1A.4 — Scheduled-vs-Unscheduled Suppression (§6.7, A3)

During an active sprint, file edits to `agents/`, `instructions/`, `templates/`,
`skills/`, `hooks/`, `scripts/`, or `schemas/` that fall **within the active
sprint's declared scope** are *scheduled* deliverables — NOT change-points — and
do NOT generate a Henkaten record.

henkaten-detector determines sprint scope by reading, in priority order:

1. `.harness/contracts/sprint-{NN}.tasks.json` (Phase 2 canonical machine-readable scope)
2. `.harness/contracts/sprint-{NN}.md` (human-readable contract; parse `## Files in Scope`)
3. `.harness/sprints.json` (sprint-level deliverable list)

If none of the above are available, the suppression rule is **bypassed**
(fail-safe — every edit fires as a Henkaten record) and the agent emits a
`coverage` warning listing which scope sources were unavailable.

Edits outside sprint scope are *unscheduled* and fire as
`agent-capability-change` Henkaten records with `change_origin: passive`.

---

## Step 1A.5 — Yokoten Review

*Source: §8.2 Step 1A.5, v2.1 amendment A9*

**Purpose:** surface lessons from prior sprints before starting the current
sprint, so that the orchestrator has an opportunity to adapt — not blindly copy.

### 1A.5.1 — Read Yokoten Blocks

Read `.council/henka-register.jsonl` and identify all records with a non-empty
`yokoten` block. A `yokoten` block contains:

- `applicable_to_subsequent_sprints` — list of sprint numbers (or `"all"`)
- `adaptation_notes` — human-readable guidance for how to adapt this learning

Filter to records where the current sprint number appears in
`applicable_to_subsequent_sprints` or where the value is `"all"`.

### 1A.5.2 — Surface Adaptation Prompts

For each applicable yokoten entry, surface an **adaptation prompt** to the
orchestrator — not a copy-paste suggestion. The retrospective agent (or the user,
per Q17 default) drafts the actual adaptation. The user reviews and ratifies.

Example prompt format:
> "Yokoten HK-{ID} from sprint {source}: '{adaptation_notes}'. How should this
> be adapted for sprint {current}?"

Log the adaptation decision to the yokoten record's `deployed_to[]` array with
timestamp, `decision_id`, and a brief `adaptation_taken` note.

### 1A.5.3 — Ratify-Once Shortcut (v2.1 A9)

If a yokoten record names **`applicable_to_subsequent_sprints: ["all"]`** OR
names **≥3 specific sprint numbers**, the user may ratify the adaptation **once**
with scope `applies_to_remaining: true`.

- After bulk ratification, the orchestrator auto-applies the same adaptation for
  each subsequent sprint with a **single-prompt confirmation**:
  *"Apply yokoten HK-{ID} to sprint {NN} as ratified? (yes/no)"*
- No per-sprint nemawashi walkthrough is required.
- The auto-application is logged to `audit-log.jsonl` as an observed action.
- The user can **revoke** the bulk ratification at any sprint boundary by
  answering `no`, which downgrades all remaining sprints back to per-sprint
  ratification.

The orchestrator does **not** execute yokoten adaptations autonomously — it
surfaces them and records the user's ratification decision.

---

## Step 1B — Delegate to /trine-eval:harness-sprint

*Source: §8.2 Step 1B*

**Purpose:** hand off sprint execution to trine-eval. The council does not enter
trine-eval's internal loop.

Invoke `/trine-eval:harness-sprint {NN}`. Wait for completion.

trine-eval's loop runs internally, covering:
- Contract negotiation (up to 2 rounds)
- Implementation by the generator agent
- Evaluation by the forked-context evaluator
- Retry loop (if the contract permits retries)
- Updates to `.harness/sprint-state.json` and `.harness/progress.md`
- Git checkpoint commit

The council is entirely external to this process. trine-eval is unaware of the
council plugin during this step.

**The autorun resumes at Step 1C ONLY after `/trine-eval:harness-sprint` reports
a sprint result** (PASS / PARTIAL / FAIL). Do not proceed to Step 1C until a
result is available. If trine-eval does not return a result (timeout, crash),
issue `andon_signal: stop` and jump to Step 1F.

---

## Step 1C — Fan-Out, Andon Handling, and Verification Spot-Check

*Source: §8.2 Step 1C, v2.1 amendments A1, A6*

**Purpose:** convene the council, collect each agent's analysis of the completed
sprint, verify observed claims, and handle any andon signals before proceeding
to course correction.

### 1C.1 — Fan-Out (Sequential Default)

Per **Q6 default**: dispatch agents **sequentially** in v0.1. Parallel dispatch
is available as a config knob (`dispatch_mode: parallel` in `.council/config.json`).

Agent dispatch order:

1. `agents/architect.md` — structural / contract alignment review
2. `agents/scope-guardian.md` — scope drift detection
3. `agents/henkaten-detector.md` — change-point classification
4. `agents/retrospective.md` — in `mini` mode (capture-only for per-sprint pass)

Each agent is dispatched as an isolated subagent via `Task`, using the
`templates/dispatch-envelope.md` envelope. Pass ONLY file paths and structured
constraints — never pass orchestrator reasoning into the subagent context.

**Andon-Swarm Dispatch is unconditionally parallel (v2.1 A6):** when an andon
signal triggers a swarm (see §1C.3), swarm agents are dispatched via **parallel
`Task` calls** regardless of `dispatch_mode` setting. Rationale: swarming is the
latency-sensitive case where the takt budget (`andon_takt_seconds`) makes
parallel dispatch necessary.

### 1C.2 — Fan-In and Evidence Check

Each agent's output is written by the orchestrator to
`.council/course-corrections/after-sprint-{NN}.md` under that agent's section.

Before accepting an agent's output, verify that it includes:
- `evidence_class` (one of `observed`, `inferred`, `speculative`)
- `confidence` (integer 1–5)
- `coverage` (list of files/paths the agent was able to examine vs. unavailable)
- For `observed` claims: a `verification` field with a re-runnable command

If an agent returned `status: error` → log the failure, skip that agent's
section, note the gap in the course-corrections file.

### 1C.3 — Andon Handling (R2/R3)

Every agent output is scanned for an `andon_signal` field. The orchestrator
MUST refer to `instructions/andon-protocol.md` for full protocol details.

**On `andon_signal: stop`:**

1. Write the thank-the-puller acknowledgment **verbatim and immediately**, before
   any analysis. Per `instructions/andon-protocol.md`:
   > "Thank you for stopping the line. Your signal has been received and will be
   > honored. No further sprint steps will proceed until this is resolved."
2. Halt the sprint loop immediately. Skip all remaining agents in the fan-out.
3. Jump to Step 1F.

**On `andon_signal: alert`:**

1. Write the thank-the-puller acknowledgment verbatim.
2. Pause the sprint loop.
3. Dispatch the **swarm** (parallel Task calls, unconditionally per A6):
   - Originating agent + any agents named in `swarm_request`
   - Total capped at 4 agents
   - Resolution window: `andon_takt_seconds` from `.council/config.json`
     (default: 600 seconds / 10 minutes per v2.1 A6)
4. If swarm resolves within the takt bound → sprint resumes. Log a decision entry
   with `andon_resolution: {originator, swarm, resolution, duration_seconds}`.
5. If swarm does NOT resolve within the takt bound → the `alert` automatically
   escalates to `stop`. Jump to Step 1F.

Pull-rate per agent is tracked in `audit-log.jsonl` (weight 2 for `stop`,
weight 1 for `alert`). See `instructions/andon-protocol.md` for anomaly
thresholds and the distinct-originator corroboration rule.

### 1C.4 — Verification Spot-Check (R4; A1)

For every agent output, identify all claims with `evidence_class: "observed"`.
From those claims, **randomly sample one** and re-run its `verification` command.

Invoke:
```
python scripts/run-verification.py "<verification_string>"
```

`scripts/run-verification.py` enforces the §7.0.2 syntax allowlist (read-only
git/grep/cat/jq/test/validation helpers) with a 10-second execution timeout and
project-root CWD. Use `--check-only` to check the allowlist without executing
(used in test isolation).

**If the verification string is NOT on the allowlist (pre-execution check):**

1. Reject the agent's claim.
2. Log an `agent-capability-change` Henkaten record via `scripts/append-henka.py`:
   ```json
   {
     "fourM_axis": "Machine",
     "change_origin": "active",
     "change_type": "agent-capability-change",
     "description": "Non-conformant verification string rejected",
     "rejected_string": "<the offending string>",
     "agent_id": "<agent>"
   }
   ```
3. Flag the agent output as partially unverified. Proceed with caution;
   do not auto-apply corrections derived from the unverified claim.
4. Ask the agent to resubmit with a conformant `verification` string.

**If the verification command runs but the result diverges from the agent's
report:** log a `quality-defect-anomaly` Henkaten with `change_origin: passive`
and high impact.

Log all spot-check results (pass or fail) to `audit-log.jsonl`.

---

## Step 1D — Reversibility Check and Course Correction Routing

*Source: §8.2 Step 1D, v2.1 amendment R9*

**Purpose:** classify each proposed correction as minor (auto-apply) or major
(nemawashi walkthrough), with reversibility as the primary gate.

### 1D.1 — Reversibility Check (Precedes Minor/Major Classification — R9)

Before classifying a correction as minor or major, determine its reversibility:

| Action | Reversibility |
|---|---|
| File writes to `.council/` working dirs, `course-corrections/`, `proposed/`, `retrospectives/`, `sessions/` | `reversible` (git revert) |
| Appends to `*.jsonl` append-only logs | `reversible-with-caveat` (entry persists; counter-entry can supersede) |
| File writes to `.harness/features.json`, `spec.md`, `sprints.json` | `reversible` per git, but Level 5 by Rule 3/7 |
| `git push`, `git push --force` | `irreversible` |
| `git reset --hard` | `irreversible` |
| `git rebase -i`, deleted pushed tags | `irreversible` (shared repos) |
| Public release / deployment | `irreversible` |

**Irreversible actions auto-escalate to MAJOR regardless of nominal class.**

### 1D.2 — Minor Corrections (Auto-Apply, Level 3, Reversible Only)

Minor AND reversible corrections may be auto-applied after a single prompt:
*"Apply minor correction X? (yes/no)"*

Minor correction examples:
- Technical notes additions to the next sprint contract
- Evaluation criterion clarifications (weight change ≤10%)
- `.council/` state file updates
- Lessons-learned entries to `progress.md`
- Noting new dependencies (informational)
- Feature status updates from `pending` → `done`

### 1D.3 — Major Corrections (Level 5 Approval, Nemawashi Stub — Sprint 6)

Major corrections OR any irreversible action require the nemawashi walkthrough
(full four-stage walkthrough is a **sprint 7 / S5 deliverable**).

**In Sprint 6 (this version), the nemawashi path is a STUB:**

1. The orchestrator creates a placeholder position paper at
   `.council/proposed/DEC-{NNNN}.md` with `nemawashi_walkthrough_version: null`
   to indicate the walkthrough has not yet been executed.
2. The path `.council/proposed/DEC-{NNNN}.md` is surfaced to the user with a
   message:
   > "Major correction DEC-{NNNN} requires nemawashi approval. A placeholder
   > has been written to `.council/proposed/DEC-{NNNN}.md`. Full walkthrough
   > support is available from sprint 7 onward. Please review and confirm
   > manually if you wish to proceed."
3. The sprint loop **halts** pending user action (Step 1F halt condition 4:
   `user_intervention_requested`).

The `nemawashi_walkthrough_version` field in the decision-log entry records:
- `null` for minor reversible auto-applied changes
- `0` for the sprint-6 stub placeholder (walkthrough not executed)
- Integer ≥1 for future versions when the full walkthrough is implemented

Major correction categories (any item below requires nemawashi or Level 5):
- Sprint reordering
- `features.json` modifications
- `spec.md` amendments
- Criteria weight changes >10%
- Adding new sprints
- Architectural pivots
- Governance rule changes
- Any irreversible action (R9)

---

## Step 1E — Decision-Log Entry

*Source: §8.2 Step 1E*

**Purpose:** record every correction, classification, and review outcome in
`decision-log.jsonl` so the audit trail is complete and the system can
reconstruct its own history without relying on conversation context.

For each change applied (minor or major), append a `DEC` entry to
`.council/decision-log.jsonl` via `scripts/append-decision.py`.

Required fields per `schemas/decision-log-entry.schema.json`:

| Field | Description |
|---|---|
| `decision_id` | Sequential `DEC-NNNN` identifier |
| `timestamp` | ISO 8601 UTC timestamp at time of logging |
| `decision_type` | e.g., `"minor-correction"`, `"major-correction"`, `"sprint-halt"`, `"andon-resolution"` |
| `decision_outcome` | `"applied"`, `"proposed"`, `"halted"`, `"deferred"`, `"rejected"` |
| `autonomy_level_used` | The level the orchestrator was operating at when the change was applied |
| `effective_autonomy_at_decision` | Level read from `.council/state/effective-autonomy.json` at the moment the decision was made |
| `reversibility` | `"reversible"` or `"irreversible"` |
| `nemawashi_walkthrough_version` | `null` for minor reversible auto-applied changes; `0` for sprint-6 stub; integer ≥1 for future full walkthrough versions |
| `description` | Human-readable summary of what was decided and why |
| `council_agents_involved` | List of agent IDs that contributed findings |
| `evidence_cited` | Array of `{evidence_class, verification, summary}` entries |
| `linked_henka_id` | HK-NNNN of the henkaten record(s) this decision responds to, if any |
| `sprint_context` | Sprint number and result (PASS/PARTIAL/FAIL) |
| `applied_automatically` | `true` for minor auto-applied; `false` for user-approved or pending |
| `user_approval_required` | `true` for major/irreversible; `false` for minor reversible |
| `affected_files` | Relative paths of files modified by this decision |

If the decision responds to a henkaten record, set `linked_henka_id` and update
that record's `resolution_status` to `"responded"` (or `"resolved"` if fully
closed). If closed, the retrospective agent populates the `yokoten` block (R6).

---

## Step 1F — Halt Conditions and Dynamic Autonomy Floor

*Source: §8.2 Step 1F, §2.4.3, v2.1 amendment A2*

**Purpose:** enumerate all conditions that require halting the sprint loop and
stopping autonomous action, including the dynamic autonomy floor drop mechanism.

The sprint loop halts if ANY of the following are true:

### Halt Condition 1 — Andon Stop (Unconditional)

`andon_signal: stop` received from any agent → **UNCONDITIONAL halt**.
No filter, no deferral, no second-guessing. See `instructions/andon-protocol.md`.

### Halt Condition 2 — Dynamic Autonomy Floor Breach (§2.4.3, A2)

The effective autonomy floor drops when the **distinct-originator corroboration
requirement** is satisfied:

- **Trigger:** three `andon_signal: stop` events within the current sprint loop,
  issued by **≥2 distinct originator agents**.
- "Distinct" means different `agent_id` values. The same agent stopping twice
  counts as **one originator**, not two.
- "Same underlying issue" is confirmed by comparing the `reason` and `evidence`
  fields of each stop signal.

**Same-agent repeated stops are NOT a floor-drop trigger.** They are tracked
as `quality-defect-anomaly` Henkaten records (`change_type: agent-capability-change`,
`fourM_axis: Machine`) — logged for pattern recognition and surfaced at the
next retrospective. A single agent cannot drop the autonomy floor alone.

**Floor-drop effect:**
- Two consecutive sprint FAILs → orchestrator drops from L4 → L3; requires user
  confirmation per sprint going forward.
- Three andon-stops from ≥2 distinct originators → all Level 2 agents drop to
  Level 1 (recommend-only); halt for human review.
- Any `change_origin: active` Henkaten flagged `high-risk` → automatic drop to
  L1 across all agents.
- **Hard halt at level 0:** when the effective autonomy level reaches 0, no
  autonomous action is permitted. Full human review is required.

When a floor drop is triggered, the orchestrator calls
`scripts/update-effective-autonomy.py` with the new level and the triggering
evidence.

Restoration: via `/council-review --restore-autonomy` flag (sprint 7 / S5
territory — document the path here; do not implement).

### Halt Condition 3 — Blocking Henkaten Unresolved

Any blocking or high-risk Henkaten record not resolved before sprint start
(detected in Step 1A) → issue `andon_signal: stop`; halt.

### Halt Condition 4 — User Intervention Required

A major correction is pending (DEC placeholder created in Step 1D.3) and Stage 4
of the nemawashi walkthrough has not been ratified → halt pending user input.

### Halt Condition 5 — Verification Spot-Check Failure Rate

If the percentage of `observed` claims failing the allowlist check across all
agents in this sprint exceeds the configured threshold (`config.max_verification_failure_rate`,
default 20%) → halt and surface the failure pattern to the user. This may
indicate a systemic agent-capability issue.

### Halt Condition 6 — Schema Validation Failure on Controlled Artifact

If `scripts/append-henka.py` or `scripts/append-decision.py` returns non-zero
exit code → halt before the record is partially written. Do not retry
automatically; surface the validation error to the user.

**On any halt:** write a decision-log entry with `decision_type: "sprint-halt"`,
describe the trigger and evidence, and surface to the user. The sprint does not
auto-resume. Restart requires explicit `/council-review` invocation.

The `nemawashi_walkthrough_version` field in the halt's decision-log entry:
`null` if the halt was not nemawashi-related; `0` if the halt was triggered by a
pending sprint-6 nemawashi stub; ≥1 for future versions.

---

## Step 1G — Context Compaction

*Source: §8.2 Step 1G*

**Purpose:** snapshot the session's working context so that future sessions can
resume without relying on conversation history (which may be compacted or lost).

Context compaction runs **unconditionally** after every sprint, regardless of
sprint result.

### What to Preserve

- Sprint number and result (PASS / PARTIAL / FAIL)
- All verdicts from the council fan-out (per agent)
- Open Henkaten records (unresolved at sprint end)
- Unresolved decisions (pending nemawashi or user approval)
- Active halt conditions
- Any standard-work changes applied this session
- Current effective autonomy level and any floor transitions

### What to Discard

- Implementation details and tool-call history
- Agent reasoning traces (preserve conclusions, not reasoning)
- Full eval report text (preserve verdict + key evidence only)
- Contract negotiation discussion
- Conversation preamble / overhead

### Compaction Target

Compact to ≤500 words in the session snapshot file.

### Output Location

Write the snapshot to:
```
.council/sessions/<UTC-ISO8601>.md
```

Example: `.council/sessions/2026-05-09T14:32:00Z.md`

The session file is the source of resumption for future sessions, but `.harness/`
and `.council/` structured files (jsonl logs, state files) are always the
authoritative source of truth and are re-read on session resume.

---

## Step 1H — Per-Sprint Mini Retrospective

*Source: §8.2 Step 1H, v2/R7*

**Purpose:** capture a brief retrospective immediately after every sprint, inline
and without blocking the orchestrator.

Call `/henkaten-council:council-retro-mini` (full implementation is a sprint 8 /
S6 deliverable; in sprint 6 this is a stub).

**Sprint 6 stub behavior:**
- Append a brief mini-retro file to:
  ```
  .council/retrospectives/sprint-{NN}-mini.md
  ```
- File contents: sprint number, sprint result (PASS/PARTIAL/FAIL), UTC timestamp,
  and a single-line summary placeholder.
- Example:
  ```markdown
  # Sprint {NN} Mini Retrospective
  Sprint: {NN}
  Result: PASS
  Timestamp: 2026-05-09T14:35:00Z
  Summary: (no council-retro-mini skill yet; stub entry)
  ```

**Constraints:**
- Maximum wall-clock time: ≤30 seconds
- No user input required; runs inline at end of every sprint
- No standard-work proposals (those are pdca/jishuken retrospective modes only)
- The retrospective agent runs in `mini` mode — Learning Points and Pattern
  Observations only, no Standard Work Proposals

---

## Step 1I — Next-Sprint or Per-Cycle Trigger Logic

*Source: §8.2 Step 1I*

**Purpose:** determine whether to invoke another sprint iteration, trigger a
per-cycle retrospective, or surface a final summary.

### Trigger Logic

| Condition | Action |
|---|---|
| More sprints in `sprints.json` + no active halt | Prompt user: *"Sprint {NN} complete. Proceed to sprint {NN+1}? (yes/no)"* If yes, return to Step 1A for the next sprint. |
| Sprint count divisible by `cycle_length` (default 5) | Invoke `/henkaten-council:council-retro` for the per-cycle PDCA retrospective before the next sprint (sprint 8 / S6 delivers the full skill; sprint 6 skips this invocation with a log note) |
| All sprints complete | Present final summary. Suggest `/henkaten-council:council-retro` (final cycle) and optionally `/henkaten-council:council-jishuken` |
| Active halt condition | Present halt reason and evidence. Wait for explicit user input. Do not auto-resume. |

### Important: No Automatic Recursive Invocation

This skill must NOT recursively invoke itself. The next-sprint loop is
**operator-driven** — the user explicitly initiates a new council-autorun
invocation for each sprint, or the orchestrator prompts and waits for a `yes`
response before proceeding to the next sprint. Automatic recursive
self-invocation would bypass human oversight and is explicitly prohibited.
The trigger logic here is documentation only; actual loop scheduling is
operator-driven.

### Per-Cycle Cadence

When the cycle trigger fires (sprint count divisible by `cycle_length`), the
per-cycle PDCA retrospective runs before the next sprint's Step 1A. This allows
standard-work proposals to emerge from the retrospective and be incorporated into
the next sprint's contract before it is negotiated.

---

## Cross-References

This skill depends on and coordinates with the following files:

| Dependency | Purpose |
|---|---|
| `instructions/andon-protocol.md` | Full andon signal protocol: thank-the-puller acknowledgment, Rule 4 carve-out, pull-rate tracking, distinct-originator corroboration |
| `scripts/run-verification.py` | §7.0.2 allowlist enforcement, 10s timeout, `agent-capability-change` Henkaten logging for non-conformant strings |
| `scripts/append-henka.py` | Append-only writer for `.council/henka-register.jsonl` |
| `scripts/append-decision.py` | Append-only writer for `.council/decision-log.jsonl` |
| `scripts/update-effective-autonomy.py` | Updates `.council/state/effective-autonomy.json` when the autonomy floor changes |
| `agents/orchestrator.md` | Orchestrator identity, tool grants, autonomy level (L4) |
| `agents/architect.md` | Structural review agent (L2, fork context) |
| `agents/scope-guardian.md` | Scope drift detection agent (L2, fork context) |
| `agents/henkaten-detector.md` | Change-point classification agent (L1, fork context) |
| `agents/retrospective.md` | Retrospective capture agent (L2, fork context, mini mode here) |
| `schemas/decision-log-entry.schema.json` | Schema for decision-log entries (Step 1E) |
| `schemas/henka-record.schema.json` | Schema for henkaten records (Steps 1A, 1C) |
| `templates/dispatch-envelope.md` | Standardized subagent dispatch template (Step 1C) |
| `templates/nemawashi-position-paper.md` | Position paper template for major decisions (Step 1D stub) |

---

## Out of Scope (Sprint 6)

The following behaviors are **documented** in this skill but **not implemented**
in sprint 6. They are stubs or references only:

- **Full nemawashi walkthrough** (Steps 1D Stages 1–4) — sprint 7 / S5.
  Sprint 6 ships a stub that creates a DEC placeholder with
  `nemawashi_walkthrough_version: null`.
- **`/council-retro` per-cycle PDCA** — sprint 8 / S6. Referenced in Step 1I.
- **`/council-retro-mini` skill** — sprint 8 / S6. Step 1H uses a stub.
- **`/council-review --restore-autonomy`** — sprint 7 / S5. Mentioned in Step 1F.
- **Live `.council/` directory** — `.council/` does not exist in this plugin
  repo. All write-path behaviors target a consumer project's `.council/`
  directory. This file is descriptive documentation only.
