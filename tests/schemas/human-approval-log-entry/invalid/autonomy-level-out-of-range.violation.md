# Violation: autonomy-level-out-of-range

## Rule violated
`effective_autonomy_at_request` must be an integer with `minimum: 0` and `maximum: 5`.
This fixture sets `effective_autonomy_at_request: 6`, which exceeds the maximum.

## Expected jsonschema error keyword
`maximum`

## Spec section
§11.7 human-approval-log-entry schema; R10 (effective autonomy level 0–5 constraint).
