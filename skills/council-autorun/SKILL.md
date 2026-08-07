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

## Step 1A.6 — Sprint Prebrief Classification

*Source: ADR-0003. Audit-only at this stage; does not change dispatch fan-out
or the autonomy floor.*

**Purpose:** record a Cynefin classification of the upcoming sprint so that
audit data captures the Orchestrator's prospective read of the work. The
classification is informational; it does not modify any downstream council
behavior at this stage.

### 1A.6.1 — Read inputs

Read at minimum:

- `.harness/contracts/sprint-{NN}.md` — the sprint contract describing
  the deliverable.
- `.council/standard-work.json` — active procedures, loop-shapes, and
  failure patterns.
- Yokoten-relevant records surfaced in Step 1A.5 above.

Optionally also: prior `.council/sprint-prebrief/sprint-{NN-1}.json`,
`.council/jishuken/*.md` artefacts relevant to the upcoming work.

### 1A.6.2 — Classify per the rubric

Apply `@instructions/sprint-prebrief.md` to select one of `clear`,
`complicated`, `complex`, or `chaotic`. Confidence is required and may
be low; honest uncertainty is preserved as `confidence: <0.5` rather
than inflated to avoid the appearance of uncertainty.

Name the expected loop-shape: either a `shape_id` from
`standard-work.loop_shapes[]` (e.g. `plan-then-execute-loop`,
`probe-campaign`) or the literal value `"ad-hoc"` when no named shape
fits.

### 1A.6.3 — Write the prebrief

Write `.council/sprint-prebrief/sprint-{NN}.json` per the schema in
`schemas/sprint-prebrief.schema.json`. Fields:

- `sprint_number`, `classified_at` (ISO 8601 UTC), `classified_by_agent`
- `cynefin`, `confidence`, `rationale` (one paragraph citing the
  specific characteristics that informed the label)
- `expected_loop_shape`
- OPTIONAL: `projection_manifest` (paths read for this classification),
  `stabilization_note` (when `cynefin: "chaotic"`),
  `autonomy_floor_observed` (captured for later analysis;
  classification does NOT adjust the floor at this stage)

The file is overwritten on re-run for the same sprint number (it is
state, not an append-only log).

### 1A.6.4 — Surface to user

Present the classification to the user inline in the autorun output,
e.g.:

> "Sprint {NN} prebrief: cynefin = `{label}` (confidence {value}).
> Expected loop-shape: `{shape_id_or_ad-hoc}`. Rationale: {one paragraph}."

If `cynefin: "chaotic"` with confidence ≥ 0.6, additionally surface:

> "Recommendation: stabilization step before proceeding. The autorun
> loop does not halt automatically at this stage (ADR-0003); the user
> may choose to halt and address the chaotic-class conditions before
> trine-eval delegation."

### 1A.6.5 — Mid-sprint mis-classification

The prebrief is frozen at sprint entry. If during execution the
Orchestrator observes that the classification was wrong, do NOT
rewrite the prebrief. Instead append a henka-record with
`fourM_axis: "Method"`, `category: "classification-mismatch"`,
`change_origin: "passive"`, and evidence citing the original prebrief
file. The mismatch is then propagated through the standard yokoten
and PDCA pathways.

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
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/run-verification.py "<verification_string>"
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

### 1D.3 — Major Corrections (Level 5 Approval, Full Nemawashi Walkthrough — Sprint 7)

Major corrections OR any irreversible action require the four-stage nemawashi
walkthrough (§8.2 Step 1D, R5). The walkthrough is defined in full below.

**Irreversible-action auto-escalation (§2.4.2, R9):** The reversibility check
(Step 1D.1) precedes the minor/major classification. If the proposed action's
reversibility is `irreversible`, the orchestrator MUST initiate the 4-stage
mandatory nemawashi walkthrough even if the nominal scope says `minor`. No
exception exists for truly irreversible changes — they always escalate to the
major path and require Level 5 (human) approval via Stage 4.

**Single-prompt minor approval path (Q15):** For a reversible minor change with
effective-autonomy level ≥ 4, no position paper is created. The orchestrator
prompts the user with a one-line summary: *"Apply minor correction X? (yes/no)"*
and applies on confirmation. The DEC entry for this path has:
- `decision_type: course-correction-minor`
- `nemawashi_walkthrough_version: null`
- `reversibility: reversible`

The literal `nemawashi_walkthrough_version: null` MUST appear in the DEC entry
for the single-prompt minor path (not 0, not omitted — exactly `null`).

**Major correction categories** (any item below requires nemawashi or Level 5):
- Sprint reordering
- `features.json` modifications
- `spec.md` amendments
- Criteria weight changes >10%
- Adding new sprints
- Architectural pivots
- Governance rule changes
- Any irreversible action (R9)

---

### Stage 1 — Write Position Paper

*Source: §8.2 Step 1D Stage 1, R5, A4*

**The orchestrator writes the full position paper BEFORE presenting anything
to the user.** The position paper is the orchestrator's complete analysis, with
every agent's perspective and evidence chain, organized so the user can form an
independent judgment.

**File location:** `.council/proposed/DEC-{NNNN}.md`
- DEC-NNNN uses a 4-digit (or more) zero-padded counter (e.g., `DEC-0042`)
  matching the pattern `^DEC-[0-9]{4,}$`, consistent with the decision-log
  schema in `schemas/decision-log-entry.schema.json`.
- Use `templates/nemawashi-position-paper.md` as the scaffold.

**The position paper must include:**
1. **Proposed change** — clear, specific description of what would be different
   after the change is applied. Which files are affected? What is the scope?
2. **Trigger / motivation** — which agent's analysis surfaced this need, and
   what evidence drove it (with `evidence_class`, `confidence`, and conformant
   `verification` commands per §7.0.2 allowlist).
3. **Reversibility assessment** — classification per Step 1D.1 table. If
   `irreversible`: explain why and note that mandatory nemawashi applies.
4. **Per-agent perspectives with evidence chains** — for each contributing
   agent: finding, evidence class + confidence + verification command, and the
   agent's view on the proposed change.
5. **Consensus chain** — how the individual perspectives converge or diverge;
   residual uncertainty.
6. **Affected artifacts table** — file paths, change type, reversibility.

After writing the position paper, surface to user:
> *"I've drafted a proposal at `.council/proposed/DEC-{NNNN}.md`. May I walk
> you through each agent's perspective before asking for approval? (yes/no)"*

If the user says `no`, the sprint loop halts (Step 1F halt condition 4:
`user_intervention_requested`) with the position paper left in place.

---

### Stage 2 — Sequential Agent Presentation

*Source: §8.2 Step 1D Stage 2, R5*

**Dispatch order matches Step 1C fan-out:**
1. architect
2. scope-guardian
3. henkaten-detector
4. retrospective
5. (Other active agents as named in `.council/council-manifest.json`)

**For each agent, the orchestrator reads the corresponding perspective from
the position paper and presents it to the user with the three-handle prompt:**

> *"[Agent Name] reviewed the sprint results and found: [brief summary of
> finding and evidence]. [Agent Name]'s view is that [perspective on the
> proposed change].*
>
> *Does [Agent Name]'s framing match your understanding? (yes / refine / disagree)"*

**Three-handle responses:**

- `yes` — Record agreement in the position paper's Stage 2 section. Proceed
  to the next agent's perspective.
- `refine` — Record the specific refinement the user offers. Re-present the
  agent's perspective with the refinement incorporated. If the user accepts
  the re-presented version (`yes`), record as "yes after refine" — no Stage 3
  needed for this agent. Multiple `refine` handles accepted in-line in Stage 2
  do NOT require Stage 3.
- `disagree` — Record the disagreement with the user's stated reason. Continue
  to the next agent. Accumulate all disagreements; advance to Stage 3 after
  all agents have been presented.

**All three-handle responses are logged to `.council/audit-log.jsonl`** via the
log-tool-call hook (sprint 5). Each log entry records: `dec_id`, `agent_id`,
`stage`, `handle`, `timestamp`, and (for `refine`/`disagree`) the user's
stated reason.

**Stage 2 outcome determination:**
- All agents `yes` (or `yes after refine`) → skip Stage 3; advance to Stage 4.
- Any agent `disagree` → advance to Stage 3 regardless of other agents' handles.

---

### Stage 3 — Alignment / Revision Loop

*Source: §8.2 Step 1D Stage 3, R5*

**Skip condition:** If all Stage 2 responses were `yes` (or `yes after refine`),
skip directly to Stage 4.

**When Stage 3 is triggered (at least one `disagree`):**

1. Summarize all disagreements and unresolved refinements from Stage 2.
2. Revise the position paper to address the disagreements.
3. Save the revised paper as a new file with `-rev{N}` suffix:
   - First revision: `.council/proposed/DEC-{NNNN}-rev1.md`
   - Second revision: `.council/proposed/DEC-{NNNN}-rev2.md`
   - Each revision is a **separate file** in `.council/proposed/`; the audit
     chain preserves all versions.
4. Return to Stage 2 with the revised paper. Re-present to ALL agents.
5. Repeat until no disagreements remain.

**Escalation-to-halt:** If alignment is not reached after 2 revision cycles
(default; configurable in `.council/config.json`), log `status: escalated-to-user`,
present remaining disagreements to the user, and HALT. Do not auto-proceed to
Stage 4.

**Multiple `refine` handles from Stage 2** are batched into a single Stage 3
revision pass — one revision file addresses all accumulated refinements.

**Track in the position paper's Stage 3 section:**
- Which agent's `disagree` or `refine` motivated each revision
- What changed in the revised paper relative to the prior version

---

### Stage 4 — Ratify Prompt and Post-Ratify Actions

*Source: §8.2 Step 1D Stage 4, R5, v2.1 amendment A4*

**Precondition:** all agent perspectives are aligned (no outstanding
`disagree` handles from Stage 2 / Stage 3).

**Ratification prompt (Orchestrator says):**

> *"All perspectives are aligned on DEC-{NNNN}. To confirm:*
>
> ***Proposed change:** {one-sentence summary}*
> ***Affected files:** {comma-separated list}*
> ***Reversibility:** {reversible / irreversible}*
>
> *Apply DEC-{NNNN}? (yes/no)"*

This is a **Level-5 (human) step**. The orchestrator blocks until the user
types `yes` or `no`.

**On `yes` (ratified):**

1. **Apply the proposed change, routing any standard-work update by `pattern_type`.**
   Read the optional `pattern_type` front-matter field from the position paper.
   When the change updates `.council/standard-work.json`, append the ratified
   entry to the array named by `pattern_type` — defaulting to `procedure` when
   the field is absent or unrecognized:

   | `pattern_type` | `standard-work.json` array | required item fields |
   |---|---|---|
   | `procedure` *(default)* | `procedures[]` | `procedure_id`, `name`, `steps` |
   | `failure-pattern` | `failure_patterns[]` | `pattern_id`, `description`, `mitigation` |
   | `evaluation-improvement` | `evaluation_improvements[]` | `improvement_id`, `description` |
   | `workflow-note` | `workflow_notes[]` | `note_id`, `description` |
   | `loop-shape` | `loop_shapes[]` | `shape_id`, `name`, `problem`, `forces`, `solution`, `consequences`, `evidence_sprints`, `status` |

   The appended entry MUST validate against `schemas/standard-work.schema.json`
   for the target array; if it does not, treat it as a ratification error — do
   not write a malformed entry, halt, and surface the schema violation. After a
   successful append, update `standard-work.json`'s `updated_at`, `updated_by`,
   and `ratified_decision_id: DEC-{NNNN}`. A decision that does not touch
   `standard-work.json` (e.g. an `irreversible-action` approval, with
   `pattern_type` omitted) applies its change directly, with no array routing.
2. Commit using this message pattern: `DEC-{NNNN}: {description}`.
3. **Move** the position paper from `.council/proposed/` to
   `.council/proposed/archive/DEC-{NNNN}.md` (or the final revision filename
   if Stage 3 was triggered — e.g., `DEC-{NNNN}-rev{N}.md`). The original
   file is **moved, not copied and not deleted**; the archive copy is the
   preserved audit record. Per v2.1 amendment A4: the `decision-log.jsonl`
   `nemawashi_walkthrough_version` path must remain resolvable at the archive
   location.
4. Append audit-log entry: *"DEC-{NNNN} position paper archived at
   `.council/proposed/archive/DEC-{NNNN}.md`"* via the log-tool-call hook.
5. Emit DEC entry via `scripts/append-decision.py` with full fields:
   - `decision_type: course-correction-major`
   - `nemawashi_walkthrough_version: {N}` — the number of Stage 3 revision
     cycles (0 if Stage 3 was never triggered, 1 if one revision was needed,
     etc.)
   - `reversibility: {reversible | irreversible}`
   - `status: ratified`
   - `applied_at: {ISO-8601 timestamp}`
   - `dec_id: DEC-{NNNN}`

**On `no` (rejected):**

1. Log `status: rejected`.
2. Do NOT apply the change.
3. The position paper remains in `.council/proposed/` for reference.
4. Emit DEC entry via `scripts/append-decision.py` with `status: rejected`,
   `applied_automatically: false`.

**Andon signals during the walkthrough:** If any agent issues
`andon_signal: stop` during Stage 1–4, the orchestrator MUST honor it
unconditionally and precede its response with the verbatim thank-the-puller
acknowledgment from `instructions/andon-protocol.md`. The walkthrough halts
and jumps to Step 1F.

**Cross-references:** `templates/nemawashi-position-paper.md`,
`.council/proposed/`, `.council/proposed/archive/`,
`scripts/append-decision.py`, `instructions/andon-protocol.md`.

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
| `decision_outcome` | `"applied"`, `"proposed"`, `"rejected"`, `"deferred"`, `"halted"`, `"superseded"` (per `schemas/decision-log-entry.schema.json`; use `"halted"` when an andon stop or harness-imposed resource cap terminates the sprint before the decision is applied) |
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
| `templates/nemawashi-position-paper.md` | Position paper template for major decisions (Step 1D Stages 1–4) |

---

## Out of Scope (Sprint 7)

The following behaviors are **documented** in this skill but **not implemented**
in sprint 7. They are stubs or references only:

- **`/council-retro` per-cycle PDCA** — sprint 8 / S6. Referenced in Step 1I.
- **`/council-retro-mini` skill** — sprint 8 / S6. Step 1H uses a stub.
- **Live `.council/` directory** — `.council/` does not exist in this plugin
  repo. All write-path behaviors target a consumer project's `.council/`
  directory. This file is descriptive documentation only.

The following were stubs in sprint 6 and are now **fully implemented** in
sprint 7:

- **Full nemawashi walkthrough** (Step 1D Stages 1–4) — implemented above.
- **`/council-review --restore-autonomy`** — implemented in
  `skills/council-review/SKILL.md` (sprint 7 / S5 deliverable).
