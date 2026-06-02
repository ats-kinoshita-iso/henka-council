# Violation: candidate loop_shapes[] entry carries a `ratified_decision_id`

## Rule violated

A `loop_shapes[]` entry with `status: "candidate"` has not been through the
nemawashi walkthrough, so it must not carry a `ratified_decision_id` — the
field must be `null` or absent. This fixture's `candidate` entry sets
`ratified_decision_id: "DEC-0007"`, which violates the conditional
(`if status == candidate then ratified_decision_id must be null`) on the
`loop_shapes[]` items schema.

## Expected jsonschema error keyword

`type`

## Spec section

ADR-0005 and the #9 follow-up. The lifecycle invariant is symmetric with the
ratified case: a candidate is by definition not yet ratified, so attaching a
ratification decision id to it is a category error that would corrupt the audit
chain. The `then` branch constrains the field to `type: "null"`, so a string
value fails with the `type` keyword.
