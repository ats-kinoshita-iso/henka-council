# Violation: event_type out of enum

## Rule violated
`event_type` must be one of the allowed enum values: `tool-call`, `andon-signal`, `andon-resolution`, `autonomy-floor-change`, `verification-spot-check`, `audit-log-rotation`, `session-start`, `session-stop`, `sprint-start`, `sprint-end`. The value `"custom-event"` is not in the enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.6 — The event_type field uses a fixed enum to categorize audit events. Non-standard event types are not permitted.
