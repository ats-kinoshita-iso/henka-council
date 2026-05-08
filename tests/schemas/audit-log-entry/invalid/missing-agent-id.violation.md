# Violation: missing required field 'agent_id'

## Rule violated
`agent_id` is a required field in `audit-log-entry.schema.json` (§11.6). Required fields are `entry_id`, `timestamp`, `event_type`, and `agent_id`.

## Expected jsonschema error keyword
`required`

## Spec section
§11.6 — Every audit log entry must identify the agent_id that generated the event, enabling pull-rate anomaly detection and accountability.
