# Violation: conflict-type-wrong-enum

## Rule violated
`conflict_type` must be one of the enumerated values: `agent-disagreement`, `evidence-contradiction`,
`scope-violation`, `governance-rule-violation`, `andon-suppressed`, `reversibility-dispute`, `custom`.
This fixture sets `conflict_type: "unknown-conflict-type"` which is not in the enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.8 conflict-resolution-entry schema — `conflict_type` enum constraint.
