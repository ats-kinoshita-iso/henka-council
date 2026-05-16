# Violation: confidence out of [0.0, 1.0] range

## Rule violated

`confidence` is constrained to the closed interval `[0.0, 1.0]` per
`schemas/sprint-prebrief.schema.json`. The value `1.5` exceeds the
maximum.

## Expected jsonschema error keyword

`maximum`

## Spec section

ADR-0003 and `instructions/sprint-prebrief.md`. Confidence is a
calibrated probability-like signal, not a free-form scalar.
Out-of-range values would degrade later analysis that aggregates
confidence across sprints to detect classifier drift.
