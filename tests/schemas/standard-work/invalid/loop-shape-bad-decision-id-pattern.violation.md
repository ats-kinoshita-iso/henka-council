# Violation: loop_shapes[] entry has a malformed `ratified_decision_id`

## Rule violated

`loop_shapes[].ratified_decision_id`, when a string, must match
`^DEC-[0-9]{4,}$` (a `DEC-` prefix followed by at least four digits). This
fixture's ratified entry sets `ratified_decision_id: "DEC-12"` (only two
digits), which violates the `pattern` constraint.

## Expected jsonschema error keyword

`pattern`

## Spec section

ADR-0005 "Out of scope" note: the link from a loop-shape to its ratifying
decision is by string convention (`^DEC-[0-9]{4,}$`), not a schema-enforced
cross-reference. The pattern is the only structural guard on that convention,
so a malformed id must be rejected to keep `ratified_decision_id` resolvable
against `decision-log.jsonl`.
