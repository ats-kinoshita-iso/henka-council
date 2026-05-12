# Violation: missing-agents.json

## Rule violated
The `council-manifest` schema requires `manifest_version`, `created_at`, and `agents`. This fixture omits `agents`, which is a required field.

## Expected jsonschema error keyword
`required`

## Spec section
§11.2 — `council-manifest.schema.json` required fields.
