# Violation: effective_autonomy_at_decision out of range (v2-specific)

## Rule violated
`effective_autonomy_at_decision` must be an integer between 0 and 5 inclusive (R10, §11.4). The value `7` exceeds the maximum allowed value.

## Expected jsonschema error keyword
`maximum`

## Spec section
§11.4, R10 — "effective_autonomy_at_decision" is a v2-required field (integer 0–5) capturing the actual effective autonomy level at decision time, which may differ from the nominal level due to dynamic floor drops. Values above 5 are not valid autonomy levels.
