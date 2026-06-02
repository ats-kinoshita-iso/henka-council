# ADR 0003: Cynefin Classification at Sprint Entry (Audit-Only)

- **Status:** Accepted
- **Date:** 2026-05-13
- **Author:** Sangen Option A integration (PR-D)
- **Scope:** A new audit signal recorded at sprint entry; one new step in
  council-autorun; no behavioral coupling at this stage

---

## Context

henka-council classifies *change-points* (henkaten) post-hoc using the 4M
axis (Man / Machine / Method / Material) at `agents/henkaten-detector.md`.
What's missing is a prospective classification of the **upcoming sprint
itself** — its complexity class, its expected shape, the kind of work it
involves. Today every sprint enters the council-autorun loop identically:
no signal distinguishes a clear-class sprint (executing a known procedure)
from a complex-class sprint (probe-and-emerge territory).

The cost of this missing signal is that:

- The Orchestrator's dispatch choices, andon thresholds, and retrospective
  framing are all calibrated for a single sprint class without
  acknowledging that classes differ.
- Future analysis cannot correlate sprint class with outcome (PASS / PARTIAL /
  FAIL), with autonomy-floor changes, with halt frequency, or with
  retrospective findings. The data simply isn't recorded.
- Mis-classifications happen invisibly: a sprint that turns out to have been
  `complex` (probe-and-emerge) is indistinguishable from one correctly
  judged `complicated` (knowable cause-and-effect) after the fact.

The sangen proposal flagged this as a real gap and proposed a Cynefin
classification at task entry. The Cynefin framework
([Snowden, 1999](https://en.wikipedia.org/wiki/Cynefin_framework)) is
domain-neutral, has stable definitions, and produces a small labelled set
(`clear` / `complicated` / `complex` / `chaotic`) that fits a single
field on a record.

---

## Decision

Add a Cynefin classification at sprint entry, recorded to
`.council/sprint-prebrief/sprint-NN.json` per
`schemas/sprint-prebrief.schema.json`, produced as a new Step 1A.6 in
`skills/council-autorun/SKILL.md` after the existing Step 1A.5 (Yokoten
Review) and before Step 1B (trine-eval delegation).

The prebrief schema captures: `sprint_number`, `classified_at`, optional
`classified_by_agent`, the `cynefin` label (`clear | complicated | complex
| chaotic`), a `confidence` value between 0.0 and 1.0, a one-paragraph
`rationale`, an `expected_loop_shape` (either a `shape_id` from
`standard-work.loop_shapes` or the literal `"ad-hoc"`), and optional
`projection_manifest`, `stabilization_note`, and `autonomy_floor_observed`
fields.

The mechanism has four parts:

### 1. Schema

`schemas/sprint-prebrief.schema.json` defines the JSON shape with the
required fields above and `additionalProperties: false`. Validation runs
through the existing jsonschema pathway (no new validator script needed
at this stage; `scripts/validate-decision-log.py` and
`scripts/validate-henka-record.py` already demonstrate the pattern, and
a similar validator can be added if append-style writes are introduced
later).

### 2. Classification rubric

`instructions/sprint-prebrief.md` (on-demand) defines the rubric: what
each Cynefin label means in henka-council's context, what signals to
look for, when to label `chaotic`, how to use low confidence honestly,
and what to do if the classification turns out to be wrong mid-sprint.

### 3. Autorun integration

`skills/council-autorun/SKILL.md` gains a new Step 1A.6 (between 1A.5
Yokoten Review and 1B trine-eval delegation). The Orchestrator reads
the sprint contract, classifies, writes the prebrief, and surfaces the
classification to the user. The step is idempotent on re-run.

### 4. Dispatch envelope and orchestrator cross-reference

`templates/dispatch-envelope.md` gains an optional "Sprint prebrief
reference" field so a dispatch can cite the prebrief artefact path.
`agents/orchestrator.md` adds `@instructions/sprint-prebrief.md` to the
Behavioral Instructions cross-reference list.

### 5. Acceptance-test extension

`tests/test-s4-acceptance.py` is extended to assert that `1A.6` appears
in the council-autorun step heading list.

---

## Consequences

### Positive

- Sprint complexity becomes a first-class audit signal recorded prospectively.
- Future analysis can correlate Cynefin class with outcome, halt
  frequency, autonomy-floor changes, and retrospective findings.
- The `expected_loop_shape` field links the prebrief to
  `standard-work.loop_shapes[]` (added in PR-C), so the classification
  also surfaces which named structural pattern the sprint expects to
  follow.
- Low-confidence classifications are first-class (the schema requires
  `confidence`, and `instructions/sprint-prebrief.md` explicitly permits
  values below 0.5). Honest uncertainty is preserved in audit data,
  rather than being hidden behind inflated labels.
- The `chaotic`-class case is named and given a recommended response
  (stabilization), so the Orchestrator has a structured way to surface
  "this work is not ready to execute as planned" without inventing the
  category each time.

### Negative / accepted

- **Early classifications will be wrong.** Cynefin is a soft framework;
  the Orchestrator's judgment will sometimes mis-label. Mitigations:
  (a) confidence is required and may be low, (b) the rubric in
  `sprint-prebrief.md` lists concrete signals per class, (c)
  mis-classifications generate a follow-up henka-record per the
  instruction, (d) the retrospective agent's PDCA mode can adapt the
  rubric if mis-classification patterns emerge.
- **The instruction lives on the on-demand surface, not auto-loaded.**
  This means agents do not have the rubric in working context unless
  they pull it in. The cost: the Orchestrator must remember to consult
  the rubric at Step 1A.6 (this is reinforced by the cross-reference
  in `orchestrator.md`). The benefit: the always-projected surface
  (governed by PR-A's projection-cost budget) does not grow.
- **One new artefact directory.** `.council/sprint-prebrief/` joins
  `.council/proposed/`, `.council/proposed/archive/`,
  `.council/course-corrections/`, `.council/retrospectives/`,
  `.council/sessions/`, `.council/jishuken/`, `.council/state/`. That
  is eight artefact directories under `.council/`. The new directory
  is at the same conceptual level as the others (a category of
  recorded artefact) and should not need consolidation.
- **Naming deliberately avoids the `sprint_context` collision.** The
  schema field of the same name (`sprint_context`) exists as an integer
  on `decision-log-entry.schema.json` and `henka-record.schema.json`
  meaning "sprint number." The new artefact directory and schema use
  `sprint-prebrief` to keep grep-ability of `sprint_context` intact.

### Deliberate non-couplings

The audit-only nature is the whole point at this stage. These couplings
are explicitly NOT introduced:

1. **No autonomy-floor adjustment.** Even when `cynefin: "chaotic"` is
   recorded with high confidence, the floor does not drop. Wiring this
   coupling prematurely risks floor adjustments based on classifier
   bias rather than observed defect.
2. **No dispatch fan-out change.** All four core agents are dispatched
   for every sprint, regardless of class. Class-conditional dispatch
   may emerge from PDCA findings but is not designed in advance.
3. **No automatic halt on `chaotic`.** The Orchestrator recommends
   stabilization but the loop continues unless the user intervenes.
4. **No mid-sprint re-classification.** The prebrief is frozen at
   sprint entry; mis-classification is captured via a follow-up
   henka-record rather than by rewriting the prebrief.

Each non-coupling can be revisited when empirical data justifies the
change. None of them are addressed in PR-D.

---

## Alternatives Considered

### Couple `chaotic` to an automatic floor drop

Rejected. Without observed data on how reliably the Cynefin classifier
identifies chaos that actually warrants floor adjustment, this would
hard-wire a classifier bias into governance. The non-coupling preserves
the option; the audit data will tell us if the coupling is justified.

### Skip the rubric and let the Orchestrator improvise

Rejected. Free-form classification across many sprints will drift
unrecognizably without an anchored rubric. A written rubric (with
explicit signals per class) is what makes the audit data analyzable;
without it, the labels lose meaning.

### Use a different complexity framework (Stacey, OODA, decision-style)

Considered. Cynefin was chosen because:
- It produces a small set of labels (four) that fit one schema field.
- It has stable, citable definitions that have been used in software-
  delivery contexts for decades.
- The four labels map cleanly to henka-council's existing concepts:
  `clear` ↔ procedures, `complicated` ↔ plan-then-execute (PR-C
  loop-shape), `complex` ↔ probe campaigns, `chaotic` ↔ stabilization
  required.

If Cynefin proves a poor fit empirically, the rubric can be replaced
with a different framework without changing the schema (the `cynefin`
field would need to be renamed in a future ADR, but the artefact
shape is stable).

### Make the prebrief append-only (a log) instead of overwritable state

Considered. Append-only would let mid-sprint re-classifications be
recorded inline. Rejected because (a) the value of the prebrief is
specifically as a frozen-in-time prospective read; (b) mis-classification
should generate a henka-record, which already has the append-only
discipline; (c) keeping `sprint-prebrief/` as state matches its
conceptual role (a snapshot per sprint, not a log of all
classifications).

### Skip PR-D entirely

Considered. The plan listed Cynefin classification as the fourth and
most prospective cherry-pick. The case for inclusion: without it, the
audit data never grows the signal that future tooling and analysis
need. With it, the audit data accumulates from PR-D merge onward, and
the question of whether to wire it into behavior can be answered
empirically rather than by guess.

---

## Trigger Conditions for Revision

This ADR should be revisited when any of the following holds:

- Audit data over ≥10 sprints shows that classification reliably
  predicts outcome (PASS / PARTIAL / FAIL) or halt frequency. The
  coupling to autonomy floor or dispatch becomes evidence-based at
  that point.
- Audit data shows the four Cynefin labels are not discriminating —
  e.g. > 80% of sprints labeled `complicated` regardless of actual
  variation. The rubric needs sharpening, or the framework needs
  replacement.
- A `chaotic`-class sprint proceeds despite the stabilization
  recommendation and produces a bad outcome. The case for wiring an
  automatic halt becomes concrete.
- The mid-sprint re-classification frequency (measured by
  `classification-mismatch` henka-records) is high enough to suggest
  the prebrief is being overproduced — maybe Step 1A.6 should be
  deferred to after the first user-visible work.
- A second project adopts henka-council with a different work pattern
  and the Cynefin rubric does not transfer. The instruction may need
  per-project tuning, or the framework may need to be generalized.

Each revision is a separate ADR that updates the schema, the
instruction, and this ADR's cross-references in turn.
