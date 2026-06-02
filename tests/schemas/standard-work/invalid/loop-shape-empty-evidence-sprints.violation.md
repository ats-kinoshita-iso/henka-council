# Violation: loop_shapes[] entry has an empty `evidence_sprints`

## Rule violated

`loop_shapes[].evidence_sprints` requires `minItems: 1` — a loop-shape must be
grounded in at least one sprint of observed evidence. This fixture sets
`evidence_sprints: []`, which violates the `minItems` constraint.

## Expected jsonschema error keyword

`minItems`

## Spec section

ADR-0005: "candidates without observed evidence are not ratifiable." The
non-empty constraint is what makes that guarantee enforceable; this fixture
pins it so the constraint cannot silently regress to accepting evidence-free
loop-shapes.
