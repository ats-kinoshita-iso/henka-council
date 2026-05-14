# ADR 0004: Five-Form Stop Conditions and decision_outcome Reconciliation

- **Status:** Accepted
- **Date:** 2026-05-13
- **Author:** Sangen Option A integration (PR-B)
- **Scope:** Schema and behavioral discipline for loop termination

---

## Context

henka-council's audit data conflates several structurally different reasons
that a sprint or council loop terminates. The existing andon protocol
distinguishes `alert` (recoverable) and `stop` (committed halt), but both
are agent-driven. There is no audit-data encoding for:

- **No-progress** — the agent's own metacognitive judgment that it cannot
  advance on the declared objective. Today this is either hidden in agent
  output text or mis-recorded as an andon stop.
- **Resource-cap** — a harness-imposed limit firing regardless of agent
  judgment (takt-window expiry, iteration cap, context-window exhaustion,
  token or time budget). Today this is implicit in the
  `andon-protocol.md` auto-escalation paragraph but has no first-class
  recording.

Separately, the existing `decision_outcome` enum has drifted across
sources. At PR-B authoring time:

- `schemas/decision-log-entry.schema.json:43` enumerated
  `["applied", "proposed", "rejected", "deferred", "superseded"]`.
- `skills/council-autorun/SKILL.md:580` documented
  `["applied", "proposed", "halted", "deferred", "rejected"]` (missing
  `superseded`, adding `halted`).
- `skills/council-review/SKILL.md:208` documented
  `["applied", "proposed", "halted"]`.
- `skills/council-kickoff/SKILL.md:291` instructed writing a seed entry
  with `decision_outcome: "council-baseline-created"` (not in any enum).
- `instructions/andon-protocol.md:266, 278` used `"resumed"` and
  `"halted-permanently"` (neither in the schema enum; `"resumed"` is the
  correct value for the separate `andon_resolution.resolution` field).

A consistent termination vocabulary required reconciling all sources and
introducing the missing distinctions in one coherent pass.

---

## Decision

Adopt a five-form loop-termination taxonomy
(**success / failure / no-progress / resource-cap / interrupt**) recorded
through extensions to existing schemas, with no new top-level
`termination_reason` field on any artefact.

The mechanism has four parts:

### 1. Extend `response_type` on henka-record

`schemas/henka-record.schema.json` adds two values to the `response_type`
enum: `"no-progress"` and `"resource-cap"`. Adds an optional
`attempts: [{approach, reason_did_not_advance}]` array. A schema-level
`if/then` clause requires `attempts` to be non-empty when `response_type`
is `"no-progress"`. All other response types treat `attempts` as
informational and optional. Backward compatible: every previously valid
record continues to validate; the `additionalProperties: false` strictness
is preserved.

### 2. Reconcile the `decision_outcome` enum

`schemas/decision-log-entry.schema.json` adds `"halted"` to the
`decision_outcome` enum without removing any existing value (final enum:
`["applied", "proposed", "rejected", "deferred", "halted", "superseded"]`).
Four downstream sources updated to match:

- `skills/council-autorun/SKILL.md:580` — table row now cites the full
  reconciled enum.
- `skills/council-review/SKILL.md:208` — same.
- `skills/council-kickoff/SKILL.md:291` — kickoff seed entry uses
  `decision_outcome: "applied"` (the legacy `"council-baseline-created"`
  was schema-invalid; semantic detail moves to the `description` field).
  The same pass also fixed `dec_id` → `decision_id` and
  `sprint_context: "kickoff"` (string) → `sprint_context: 0` (integer)
  on the same seed entry, both of which were latent schema violations
  surfaced by the audit.
- `instructions/andon-protocol.md:266, 278` — `decision_outcome` now uses
  `"applied"` or `"halted"`; the sub-object `andon_resolution.resolution`
  remains the correct location for `"resumed"`, `"escalated_to_stop"`,
  `"user_intervention"`.

### 3. Document the taxonomy

`instructions/stop-conditions.md` (new, on-demand) defines the five forms,
gives concrete examples per form, explains the agent-vs-harness encoding
via record authorship, and lists common mis-codings to avoid.

`instructions/andon-protocol.md` (modified) adds a new section
**"Andon Stop vs No-Progress vs Resource-Cap (MUST NOT conflate)"**
that draws the distinction directly inside the andon-protocol vocabulary
where readers are already calibrated on `alert` vs `stop`.

### 4. Bind the Orchestrator

`agents/orchestrator.md` (modified) adds a new sub-obligation **5a.
Loop-Termination Recording** under existing obligation 5 (Decision-Log
Writing). The sub-obligation requires the Orchestrator to write a closing
henka-record (with the appropriate `response_type`) and a linked closing
decision-log entry (with `decision_outcome: "halted"`) whenever a loop
terminates without applying a decision. The Behavioral Instructions
cross-reference list adds `@instructions/stop-conditions.md`.

---

## Consequences

### Positive

- The audit chain becomes navigable: read the closing decision-log entry,
  follow `linked_henka_id` to the closing henka-record, read
  `response_type` and any `attempts[]` for the precise termination
  encoding.
- The agent-vs-harness distinction is encoded by record authorship and
  preserved in audit data, supporting later analysis of where the loop
  termination judgment came from.
- The `decision_outcome` enum is now coherent across all five sources
  that documented it; future drift is caught by schema validation rather
  than discovered by manual grep.
- The kickoff seed entry now validates against the decision-log schema
  (three pre-existing latent bugs fixed in passing: `dec_id` →
  `decision_id`, `decision_outcome` →  enum-valid, `sprint_context` →
  integer).
- The `no-progress` form makes the agent's metacognitive judgment a
  first-class audit signal, which is load-bearing for the "the agent
  decides when it is stuck, the harness decides when it has run out of
  budget" distinction.

### Negative / accepted

- Two parallel termination vocabularies persist by design:
  - `andon_signal.type` on henka-record (`alert | stop`) for the
    in-flight signal mechanism.
  - `response_type` on henka-record (`andon-stop | no-progress |
    resource-cap | ...`) for the closing classification.
  These do not collide; they record different stages of the same lifecycle
  (signal-time vs termination-time). The two vocabularies are aligned by
  convention: an agent that issues `andon_signal: stop` and whose stop is
  honored produces a closing henka-record with
  `response_type: "andon-stop"`. The alignment is documented in
  `instructions/stop-conditions.md` but is not schema-enforced.
- The schema-level `if/then` clause for `attempts` requires `attempts` to
  be non-empty when `response_type` is `"no-progress"`. JSON-Schema Draft
  7 supports this construct, but it adds modest complexity to the
  schema. The construct was chosen over making `attempts` unconditionally
  required because most response types do not need it; pushing the
  requirement under the if/then keeps the optional path optional.
- `superseded` remains in the `decision_outcome` enum as a kept value,
  even though no current source documents its use. Removing it would
  have been a schema-narrowing change that risked invalidating any
  existing record. Future cleanup if `superseded` is genuinely unused is
  a separate concern.

### Out of scope

- **Termination-reason as a top-level field on decision-log-entry.**
  Considered and rejected (see Alternatives). The henka-record carries
  the termination encoding; the decision-log carries
  `decision_outcome: "halted"` and a `linked_henka_id` pointer.
- **Iteration caps as a fully-typed sub-enum of resource-cap.** The
  current design treats all resource-caps as one form. If audit data
  later shows the cap type matters analytically, a sub-classification
  could be added without breaking the five-form taxonomy.
- **Automatic enforcement of "did you record a closing pair when the
  loop halted?".** This is a behavioral obligation on the Orchestrator;
  it is not schema-enforced. A future hook could check that every
  decision-log entry with `decision_outcome: "halted"` has a non-null
  `linked_henka_id`. Deferred until empirical data justifies the hook.

---

## Alternatives Considered

### Put `termination_reason` on decision-log-entry as a top-level field

Rejected. A termination determination is a metacognitive observation
about the loop, which is exactly what henka-record exists to capture.
Putting it on decision-log-entry creates a parallel taxonomy that has to
be kept in sync with `response_type` on the henka side. The chosen
design keeps the termination encoding in the agent-observation domain
where it is generated, and uses the existing `linked_henka_id` field on
decision-log-entry to chain them.

### Add `no-progress` and `resource-cap` to the andon-signal type enum

Rejected. `andon_signal.type` is specifically for the in-flight signal
mechanism (alert vs stop). Conflating no-progress with stop would
collapse the agent-vs-harness distinction this ADR exists to establish.

### Strip `superseded` from the `decision_outcome` enum

Rejected. Schema-narrowing changes risk invalidating existing records.
Even if no current source documents `superseded`, an ad-hoc record may
have used it. The change is additive only.

### Drop the `if/then` schema constraint and trust the orchestrator to enforce

Rejected. Schema-level enforcement catches mis-encodings at append time
via `scripts/append-henka.py`, which already runs the validator. Trusting
the orchestrator to enforce a structural rule that the schema can
express is exactly the kind of brittleness audit-trail discipline is
meant to prevent.

---

## Trigger Conditions for Revision

This ADR's design should be revisited when any of the following holds:

- Audit data over several sprints shows agents systematically
  mis-classifying terminations (e.g., recording resource-cap when
  no-progress is the correct value). The taxonomy itself may need
  refinement, or the agent guidance may need sharpening.
- A new form of termination emerges that none of the five capture well
  — for example, a "deferred-to-future-sprint" outcome that is neither
  success, failure, no-progress, resource-cap, nor interrupt.
- The `superseded` value finally needs cleanup (zero audit occurrences
  across a quarter of activity is the trigger).
- The `attempts` requirement for `no-progress` is found to be too
  burdensome in practice — agents recording empty rationale fields to
  satisfy the constraint. The fix is sharper agent guidance, not a
  schema relaxation.

Each revision is a separate ADR that updates schemas, instructions, and
this ADR's cross-references in turn.
