# Violation: session event without `session_id`

## Rule violated
A `kind: session` event requires `session_id`, `lifetime`, `usage`, `cost_usd` and `outcome`. Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`required`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1, Schema 1.1.
