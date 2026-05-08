# Violation: level-out-of-range

## Rule violated
`level` must be an integer with `minimum: 0` and `maximum: 5`.
This fixture sets `level: 6`, which exceeds the maximum.

## Expected jsonschema error keyword
`maximum`

## Spec section
§11.11 effective-autonomy schema (NEW v2/R10) — level constraint 0–5.
