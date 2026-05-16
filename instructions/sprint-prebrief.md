# Sprint Prebrief — Behavioral Instructions

Every council sprint begins with a **prebrief**: a Cynefin classification of
the upcoming work, recorded to `.council/sprint-prebrief/sprint-NN.json`.
The prebrief is **informational at this stage** — it does not change which
agents are dispatched, the autonomy floor, or any other downstream behavior.
What it does is make the Orchestrator's prospective read of the sprint
**visible in audit data**, so that mis-classifications can be caught after
the fact and so future tooling can correlate classification with outcome.

This instruction documents the classification rubric, where the prebrief
lives, the audit trail it creates, and the deliberate non-couplings at
this stage.

---

## The Four Cynefin Classes

The classification names a single label for the upcoming sprint as a whole.

### `clear`

A known solution exists. The path is well-trodden. The work is closer to
"execute the recipe" than "figure out what to do." Typical signal: a
matching procedure or loop-shape already exists in `standard-work.json`;
the sprint can apply it with minor adaptation.

### `complicated`

The path requires expert analysis but cause-and-effect are knowable. The
work is non-trivial but not exploratory: a competent analyst (human or
agent) can reason from current state to the solution. Plan-then-execute
shapes typically fit. Typical signal: the sprint contract specifies a
deliverable that has a clear shape but requires careful design before
implementation.

### `complex`

Probe-and-emerge territory. There is no stable baseline; the recommended
solution shifts as investigation proceeds. A probe campaign is usually the
right shape (two or three safe-to-fail probes, gather results, converge
or pivot). Typical signal: the sprint contract is exploratory, with
acceptance criteria that may need refinement based on probe results.

### `chaotic`

No order is visible. Tactical action is premature; stabilization is
required first. The Orchestrator should NOT execute the sprint as planned
when this label fires with high confidence; instead it should recommend
a stabilization step to the user. **At this stage of the integration the
council-autorun loop does NOT mechanically halt on `chaotic`** — the
recommendation is surfaced but the loop continues unless the user
intervenes. See ADR-0003 for the deliberate non-coupling rationale.

---

## When the Prebrief Is Produced

At sprint entry, after yokoten review (Step 1A.5 of council-autorun) and
before fan-out (Step 1C). This is Step 1A.6 in
`skills/council-autorun/SKILL.md`. The Orchestrator:

1. Reads the upcoming sprint's contract (`.harness/contracts/sprint-NN.md`),
   the active standard-work entries
   (`.council/standard-work.json`), and any unresolved yokoten records
   identified in 1A.5.
2. Selects one of the four Cynefin labels per the rubric above.
3. Records a confidence value between 0.0 and 1.0.
4. Writes a one-paragraph rationale citing the specific characteristics
   that informed the label.
5. Names an expected loop-shape (a `shape_id` from
   `standard-work.loop_shapes` if one fits, or the literal `"ad-hoc"`).
6. OPTIONAL: captures the `projection_manifest` (which files were read
   to produce the classification) and the current `autonomy_floor_observed`.
7. Surfaces the classification to the user inline in the autorun output.
8. Appends the JSON document to `.council/sprint-prebrief/sprint-NN.json`.

The file is overwritten on re-run for the same sprint number (it is
state, not an append-only log). Prior sprint prebriefs remain available
under their own `sprint-NN.json` paths.

---

## Confidence Is Required and May Be Low

The confidence value is a required field on every prebrief. Low confidence
(e.g. < 0.5) is acceptable and is explicit signal that the classification
may need to be revised mid-sprint. The Orchestrator MUST NOT inflate
confidence to avoid the appearance of uncertainty — the audit value of
the prebrief depends on its honesty.

If confidence is below 0.5, the rationale should explicitly say so and
identify the specific source of uncertainty (e.g. "Acceptance criteria
in the sprint contract are precise but the design space for component X
is broad; classification could shift to `complex` if early implementation
reveals unknown unknowns.").

---

## Non-Couplings at This Stage

The PR-D implementation introduces classification as an audit signal
only. The following couplings are **deliberately deferred** to future
amendments:

### 1. Autonomy floor is NOT adjusted on `chaotic` or low-confidence

Even when the Orchestrator labels a sprint `chaotic` with high
confidence, the dynamic autonomy floor remains at its current value.
The reason: until we have several sprints of classification data, we
do not know whether `chaotic`-class sprints reliably correlate with
floor-drop-worthy outcomes. Wiring the coupling prematurely would risk
floor adjustments based on classifier bias rather than observed defect.

The `autonomy_floor_observed` field on the prebrief captures the
current floor so that future analysis can compare classification
against floor state retrospectively.

### 2. Dispatch fan-out is NOT changed by class

A `clear`-class sprint still dispatches the same four-agent routine
review as a `complex`-class sprint. The rationale parallels (1): until
we have evidence that class-conditional dispatch produces better
outcomes, the routine fan-out stays uniform.

### 3. No automatic halt on `chaotic`

The Orchestrator recommends stabilization on a `chaotic` classification
but does NOT halt the sprint. The user retains the choice. If
empirical data later shows that `chaotic` classifications reliably
predict bad sprint outcomes, the loop can be wired to halt at that
point.

### 4. No re-classification mid-sprint

The prebrief is recorded once, at Step 1A.6. If the sprint reveals
that the initial label was wrong, the correct response is to record a
henka-record (with appropriate `response_type` and `category`)
documenting the mis-classification. The prebrief itself is not
rewritten mid-sprint; its value is precisely as a frozen-in-time
prospective read.

---

## Cross-References

- `schemas/sprint-prebrief.schema.json` — the exact JSON shape this
  instruction governs.
- `skills/council-autorun/SKILL.md` Step 1A.6 — where the prebrief is
  produced inside the autorun loop.
- `docs/design/adr-0003-cynefin-classification.md` — design rationale
  for adding Cynefin as a separate audit signal and for the
  non-couplings above.
- `instructions/human-approval.md` — the autonomy framework the
  prebrief does NOT couple into at this stage.
- `agents/orchestrator.md` — the agent that produces the prebrief at
  sprint entry.

---

## What a Mis-Classification Looks Like (and What to Do)

If during sprint execution the Orchestrator observes that the
classification was wrong (e.g. labeled `complicated` but the work is
turning out to be `complex` probe-and-emerge):

1. Do NOT rewrite the prebrief. Its value is as a frozen-in-time
   record.
2. Append a henka-record to `henka-register.jsonl` with:
   - `fourM_axis: "Method"`
   - `category: "classification-mismatch"` (custom category)
   - `change_origin: "passive"` (the reality emerged, not deliberately
     introduced)
   - `description` citing the specific mid-sprint observation that
     revealed the mis-classification
   - `evidence` referencing the original prebrief file
3. Surface the mismatch in the next mini-retro (`council-retro-mini`),
   so the PDCA cycle can adapt classification heuristics if patterns
   emerge.

This is the audit chain working as designed: prebrief frozen,
henka-record captures the deviation, retro propagates the learning.
