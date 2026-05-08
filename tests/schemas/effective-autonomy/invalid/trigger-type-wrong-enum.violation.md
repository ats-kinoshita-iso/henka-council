# Violation: trigger-type-wrong-enum

## Rule violated
`trigger_history[].trigger_type` must be one of the enumerated values:
`consecutive-fail-drop`, `andon-stop-drop`, `high-risk-henkaten-drop`,
`restore-autonomy`, `manual-override`, `sprint-pass-restore`, `initial`.
This fixture uses `"unknown-trigger"` which is not in the enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.11 effective-autonomy schema (NEW v2/R10) — trigger_history items trigger_type enum.
