# Violation: additional property not allowed

## Rule violated
`audit-log-entry.schema.json` sets `additionalProperties: false`. The field `extra_field` is not defined in the schema's `properties` and is therefore disallowed.

## Expected jsonschema error keyword
`additionalProperties`

## Spec section
§11.6 — Audit log entries use a closed schema (additionalProperties: false) to ensure all logged fields are recognized and parseable by log processing tools.
