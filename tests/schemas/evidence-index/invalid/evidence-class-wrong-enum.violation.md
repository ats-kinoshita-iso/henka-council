# Violation: evidence-class-wrong-enum

## Rule violated
`entries[].evidence_class` must be one of `observed`, `inferred`, `speculative`.
This fixture uses `"certain"` which is not in the enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.9 evidence-index schema — entries items evidence_class enum constraint.
