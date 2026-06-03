# Violation: ratified loop_shapes[] entry missing `ratified_decision_id`

## Rule violated

A `loop_shapes[]` entry with `status: "ratified"` must carry the
`ratified_decision_id` of the nemawashi decision that ratified it. This
fixture's entry is `ratified` but omits `ratified_decision_id`, which violates
the conditional (`if status == ratified then ratified_decision_id is required`)
added to the `loop_shapes[]` items schema.

## Expected jsonschema error keyword

`required`

## Spec section

ADR-0005 (`docs/design/adr-0005-loop-shape-pattern-category.md`) and the #9
follow-up. `status` and `ratified_decision_id` together encode the audit chain:
a ratified loop-shape must be traceable to the Stage-4 nemawashi decision that
approved it. A ratified entry without that link is unattributable — the schema
now rejects it rather than accepting an orphaned "ratified" record.
