# Violation: missing required field 'procedures'

## Rule violated
`procedures` is a required field in `standard-work.schema.json` (§11.5). The schema also requires `version` and `updated_at`.

## Expected jsonschema error keyword
`required`

## Spec section
§11.5 — standard-work.json must include a `procedures` array (minItems: 1) defining the council governance step-by-step procedures.
