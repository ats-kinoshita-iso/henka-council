# Violation: version wrong type (integer instead of string)

## Rule violated
`version` must be a string matching the pattern `^[0-9]+\.[0-9]+\.[0-9]+$` (semver format). The value `1` is an integer, not a string.

## Expected jsonschema error keyword
`type`

## Spec section
§11.5 — standard-work.schema.json requires `version` as a string with semver pattern validation.
