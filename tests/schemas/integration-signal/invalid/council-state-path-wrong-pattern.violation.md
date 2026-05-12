# Violation: council-state-path-wrong-pattern

## Rule violated
`governance.council_state_path` must match the pattern `^\.council/$` (must be exactly `.council/`).
This fixture uses `"council/state/"` which does not start with `.council/`.

## Expected jsonschema error keyword
`pattern`

## Spec section
§11.10 integration-signal schema — council_state_path pattern constraint requiring `.council/` path.
