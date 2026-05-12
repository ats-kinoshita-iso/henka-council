# Violation: enum-out-of-range-review-frequency.json

## Rule violated
The `review_frequency` property must be one of `["every-sprint", "every-other-sprint", "manual"]`. This fixture provides `"per-commit"` which is not in the allowed enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.1 — `council-config.schema.json`. The `review_frequency` property is defined with `"enum": ["every-sprint", "every-other-sprint", "manual"]`.
