# Violation: missing reversibility (v2-specific)

## Rule violated
`reversibility` is a required field in `decision-log-entry.schema.json` (R9, §11.4). Irreversible decisions must auto-escalate to Level 5 regardless of nominal level — the field is mandatory for governance enforcement.

## Expected jsonschema error keyword
`required`

## Spec section
§11.4, R9 — "reversibility" enum ["reversible", "irreversible"] is a v2-required field that was absent in v1. Omitting it prevents the governance layer from applying the irreversibility escalation rule.
