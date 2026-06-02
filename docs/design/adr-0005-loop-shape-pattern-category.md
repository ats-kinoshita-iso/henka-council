# ADR 0005: Loop-Shape as a Saturable Pattern Category

- **Status:** Accepted
- **Date:** 2026-05-13
- **Author:** Sangen Option A integration (PR-C)
- **Scope:** `schemas/standard-work.schema.json` and the retrospective →
  nemawashi → standard-work pipeline

---

## Context

`.council/standard-work.json` currently records several categories of
canonical guidance: `procedures[]` (ordered step lists),
`failure_patterns[]`, `evaluation_improvements[]`, `workflow_notes[]`, and
`sizing_heuristics`. None of these capture **how a loop is structured** —
the reusable shape of a multi-phase work pattern, distinct from the
specific procedural steps of any one task.

Examples of loop-shapes that emerged from observation across sprints:

- **Plan-Then-Execute Loop** — non-trivial work where the cost of going in
  the wrong direction is high; producer drafts a plan, plan is reviewed,
  execution proceeds against the approved plan.
- **Probe Campaign** — complex-class work where two or three safe-to-fail
  probes are launched in parallel, results are gathered, and the campaign
  converges or pivots.
- **Verify-Until-Pass** — quality-critical work where iteration continues
  until an external criterion is met.

These shapes share structure across many specific tasks and benefit from
being named, captured, and ratified the same way procedures are. They
also have a structural form that procedures don't: the classical
pattern-language fields (problem / forces / solution / consequences /
when-not-to-use), which capture the recurring problem the shape solves
rather than the steps to execute it.

The Discovery Gate design (`docs/design/discovery_gate.md`) and the
retrospective agent's PDCA-mode outputs both surface candidates that
look like loop-shapes but have no canonical place to live in
`standard-work.json`. PR-B introduced `response_type: "no-progress"` and
`"resource-cap"` on henka-records, which makes loop termination a
first-class audit signal — recognizing recurring loop-shapes is the
natural complement.

---

## Decision

Add a new optional top-level array `loop_shapes[]` to
`schemas/standard-work.schema.json`, with the pattern-language structure
(problem / forces / solution / consequences / when-not-to-use), an
evidence-sprints array, a ratification-decision-id link, and a lifecycle
status (`candidate | ratified | deprecated`).

Loop-shape candidates ratify through the **same** 4-stage nemawashi
walkthrough as procedures. No parallel ratification machinery is added.
The nemawashi position paper template (`templates/nemawashi-position-paper.md`)
gains an optional `pattern_type` front-matter field that declares which
standard-work array a Stage 4 ratification updates, so the existing
walkthrough machinery routes correctly without needing to inspect content.

*Implementation note (issue #9 follow-up):* this routing is realized in
`skills/council-autorun/SKILL.md` § "Stage 4 — Ratify Prompt and Post-Ratify
Actions": on ratify, Stage 4 reads `pattern_type` and appends the entry to the
named `standard-work[]` array (default `procedure`). The discriminator is the
structured field, so no free-text content parsing is required — but the switch
must be present for the "routes correctly" claim to hold. It was originally
documented on the position paper but not read by the skill; that gap is now
closed and guarded by `tests/test-stage4-routing.py`.

The retrospective agent (`agents/retrospective.md`) and the PDCA template
(`templates/retrospective-pdca.md`) are updated to note that loop-shape
candidates can be surfaced in the Act phase alongside other standard-work
proposals.

A schema fixture (`tests/schemas/standard-work/valid/example-with-loop-shapes.json`)
demonstrates the array with one candidate and one ratified entry. A
negative fixture (`tests/schemas/standard-work/invalid/loop-shape-missing-status.json`)
demonstrates that the `status` field is required.

---

## Consequences

### Positive

- Recurring loop structures can be named, recorded with evidence,
  ratified, and propagated through the same audit chain that procedures
  use. The yokoten propagation mechanism (`schemas/henka-record.schema.json`'s
  `yokoten` field) extends naturally to loop-shape deployment across
  sprints.
- The pattern-language structure (problem / forces / solution /
  consequences / when-not-to-use) is the right shape for capturing
  WHY a structural choice is made, complementing procedures' WHAT.
- The `evidence_sprints[]` array enforces that loop-shapes are
  grounded in observation, not invention. The PR-C schema requires
  `minItems: 1` for `evidence_sprints` — a loop-shape candidate without
  observed evidence is not ratifiable.
- The `pattern_type` field on nemawashi position papers makes the
  routing explicit at Stage 1 (when the position paper is drafted), so
  the Stage 4 ratification machinery does not need to guess which
  standard-work array to update.
- Backward-compatible: the array is optional and may be empty or absent;
  every existing `standard-work.json` continues to validate unchanged.

### Negative / accepted

- **Sibling-array proliferation.** `standard-work.json` now has six
  sibling categories at top level: `procedures[]`, `failure_patterns[]`,
  `evaluation_improvements[]`, `workflow_notes[]`, `sizing_heuristics`,
  and now `loop_shapes[]`. This is the known-not-ideal outcome the plan
  agent flagged during PR design review. The reason we accept it: the
  alternative — unifying all six under a single `patterns[]` array with
  a `pattern_type` discriminator — is a breaking schema refactor that
  would invalidate every existing `standard-work.json` record. The
  consolidation is a defensible v2 direction; doing it here would
  bloat PR-C's scope by an order of magnitude. The known-future-work
  is tracked in this ADR's "Trigger conditions for re-baseline" below.
- **Pattern-language vs. step-list duplication.** A given canonical
  work guidance could theoretically be expressed either as a procedure
  (ordered steps) or as a loop-shape (pattern language). The PR-C
  guidance: use `procedures[]` for "do these steps to accomplish X"
  and `loop_shapes[]` for "this is a reusable structure for a class of
  multi-phase work." If an author can naturally write both, the
  pattern-language form usually fits — procedures degrade poorly when
  the steps depend on context, whereas pattern-language forms encode
  the tradeoffs that make context-sensitivity legible.
- **No automated guard against mis-categorization.** The schema does
  not enforce a structural boundary between procedures and loop-shapes
  beyond field shape. An author could put pattern-language content in
  a `procedures[]` entry's `description` field and it would validate.
  Mitigation: the retrospective agent's instructions and the PDCA
  template explicitly distinguish the two; the nemawashi walkthrough's
  Stage 2 per-agent review catches mis-categorization in practice.
- **`pattern_type` is optional.** The nemawashi position paper's new
  `pattern_type` field is OPTIONAL on the principle of backward
  compatibility — existing position papers do not have it and should
  not be invalidated retroactively. New position papers that target a
  specific standard-work array should set it; non-standard-work
  decisions (e.g. autonomy-floor restore) leave it absent.

### Out of scope

- **Unifying the six standard-work arrays under a single `patterns[]`
  discriminator.** Tracked as a known consolidation direction; not
  addressed here. See trigger conditions below.
- **A schema-level link from `loop_shapes[].ratified_decision_id` to
  the decision-log entry that ratified it.** The link is by string
  convention (pattern `^DEC-[0-9]{4,}$`), not by schema-enforced
  cross-reference. JSON Schema Draft 7 does not natively support
  cross-document references for this kind of audit chain; a future
  validation script could check resolvability.
- **Loop-shape deprecation discipline.** The `status: deprecated`
  value is reserved for retired patterns kept for audit traceability,
  but the formal deprecation flow (when does ratified → deprecated
  happen, who decides, what evidence is required) is not specified in
  PR-C. The first deprecation event will surface the need; until then
  the value exists to keep the lifecycle complete without forcing the
  question.
- **Cross-session and cross-project loop-shape sharing.** Loop-shapes
  are ratified within a single project's `.council/standard-work.json`.
  Sharing across projects would need either manual copy or a registry
  mechanism; both are deferred.

---

## Alternatives Considered

### Add `loop-shape` as a `pattern_type` discriminator on `procedures[]` entries

Rejected. The classical pattern-language form (problem / forces /
solution / consequences / when-not-to-use) is genuinely distinct from
the procedure form (ordered step list). Forcing both into the same
array schema requires either:

- Making most fields optional, weakening the schema for both forms; or
- Splitting via `oneOf` / `anyOf` inside a single array, which is
  structurally what a discriminator achieves but with more JSON-Schema
  ceremony than two top-level arrays.

The clean separation outweighs the duplication cost. The discriminator
approach can be revisited if/when the consolidation refactor happens.

### Use the existing `workflow_notes[]` array

Rejected. `workflow_notes[]` entries are free-form `{note_id, description}`
pairs; the pattern-language structure does not fit. Forcing loop-shapes
into workflow_notes would either lose the structure (just dump
everything into `description`) or expand workflow_notes' schema to be
indistinguishable from a new top-level array.

### Add loop-shapes as a separate file (`.council/loop-shapes.json`)

Rejected. The ratification flow already targets
`.council/standard-work.json`; splitting loop-shapes into a sibling file
would require parallel ratification machinery, parallel git tracking,
and parallel yokoten propagation. The cost outweighs the benefit of
keeping `standard-work.json` smaller.

### Require `evidence_sprints[]` to have `minItems: 3` (sangen's saturation rule)

Considered. Sangen's saturation flow requires evidence from "at least
three independent successful loops drawn from at least two distinct
sessions" before naming. Henkaten-council does not have sangen's session
concept (it has sprints), so the analogue would be `minItems: 3` on
`evidence_sprints[]`. We chose `minItems: 1` instead because:

- A single-sprint candidate is a legitimate observation that deserves
  capture, even if it is not yet ratifiable. The `status: candidate`
  is the gate that prevents premature ratification, not the
  evidence-sprints count.
- The nemawashi walkthrough already requires "≥2 sprints of evidence
  (or 1 sprint with strong deterministic evidence and explicit
  justification)" per `agents/retrospective.md`. Enforcing a stricter
  schema rule would create a discrepancy between schema and behavioral
  policy.
- Tightening to `minItems: 3` later is a small, additive change. Loosening
  is harder.

---

## Trigger Conditions for Re-Baseline / Future Consolidation

This ADR should be revisited when any of the following holds:

- A clear majority of loop-shape candidates also naturally express as
  procedure candidates. That signals the schema separation is creating
  artificial duplication and the consolidation refactor is warranted.
- The six standard-work arrays grow to seven or more. Sibling-array
  proliferation past six is a smell; consolidation pressure increases.
- A second project adopts henka-council and needs to share loop-shapes.
  Cross-project sharing surfaces the registry question.
- A loop-shape is deprecated for the first time. The formal deprecation
  flow can be specified then, grounded in the actual case.

Each revision is a separate ADR that updates schemas, instructions, and
this ADR's cross-references in turn.
