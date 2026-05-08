# Violation: wrong-type-autonomy-level.json

## Rule violated
The `autonomy_level` property must be an integer (0–5). This fixture provides a string `"four"` instead of an integer.

## Expected jsonschema error keyword
`type`

## Spec section
§11.1 — `council-config.schema.json`. The `autonomy_level` property is defined as `{"type": "integer", "minimum": 0, "maximum": 5}`.
