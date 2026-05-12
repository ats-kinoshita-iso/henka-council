# Violation: missing-governance

## Rule violated
`governance` is the only required top-level property. This fixture omits it entirely,
placing `enabled` at the top level instead of nested inside `governance`.

## Expected jsonschema error keyword
`required`

## Spec section
§11.10 integration-signal schema — `required: ["governance"]` top-level constraint.
