# Violation: `lifetime.coverage` without `shortfall`

## Rule violated
Every key of `lifetime.coverage` is required (`definitions.coverage.required`): a reader must
see where the transcript holds more tokens than the cost-state delta, even when the list is
empty. Otherwise `valid/session-settled.json`.

## Expected jsonschema error keyword
`required`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1 D1.8.
