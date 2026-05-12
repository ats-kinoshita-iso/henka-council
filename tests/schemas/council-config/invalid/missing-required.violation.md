# Violation: missing-required.json

## Rule violated
The `council-config` schema requires four properties: `council_version`, `target_project`, `autonomy_level`, and `review_frequency`. This fixture omits `council_version` and `review_frequency`.

## Expected jsonschema error keyword
`required`

## Spec section
§11.1 — `council-config.schema.json` required fields. The `required` array in the schema lists `["council_version", "target_project", "autonomy_level", "review_frequency"]`.
