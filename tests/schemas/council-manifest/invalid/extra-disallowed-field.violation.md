# Violation: extra-disallowed-field.json

## Rule violated
The schema uses `"additionalProperties": false` at the top level and within agent items. This fixture contains an extra top-level key `undocumented_key` and an extra agent-level key `secret_mode`, both of which are disallowed.

## Expected jsonschema error keyword
`additionalProperties`

## Spec section
§11.2 — `council-manifest.schema.json`. Both the manifest object and agent item objects declare `"additionalProperties": false`.
