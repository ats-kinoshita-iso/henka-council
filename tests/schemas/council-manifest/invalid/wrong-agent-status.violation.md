# Violation: wrong-agent-status.json

## Rule violated
Each agent in the `agents` array must have a `status` that is one of `["active", "proposed", "disabled"]`. This fixture uses `"running"` which is not a valid enum value.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.2 — `council-manifest.schema.json`. The `status` property within agent items is defined with `"enum": ["active", "proposed", "disabled"]`.
