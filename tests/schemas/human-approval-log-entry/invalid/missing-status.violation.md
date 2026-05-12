# Violation: missing required field 'status'

## Rule violated
`status` is a required field in `human-approval-log-entry.schema.json` (§11.7). Required fields are `approval_id`, `timestamp`, `approval_type`, and `status`.

## Expected jsonschema error keyword
`required`

## Spec section
§11.7 — Every human approval log entry must record the outcome status (approved, rejected, revised, or pending).
