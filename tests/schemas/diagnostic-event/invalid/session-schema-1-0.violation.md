# Violation: a `kind: session` event at `schema_version` 1.0

## Rule violated
A session event must be schema 1.1 (`const`). The 1.0 rule also forbids `lifetime`, `cost_state_usage_by_model` and `counts.tool_failures_by_tool`, so those `false` schemas fail as well; the documented reason is the version.

## Expected jsonschema error keyword
`const`

## Spec section
ADR-0006 A1, Schema 1.1 and Verification: a kind: session event with schema_version 1.0 is rejected.
