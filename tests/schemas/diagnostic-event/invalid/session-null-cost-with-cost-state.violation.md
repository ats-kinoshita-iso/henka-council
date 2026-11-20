# Violation: a null cost that still carries `cost_state_usage_by_model`

## Rule violated
A null-cost event carries no other cost-state figure: `cost_state_usage_by_model` is forbidden (a `false` schema). Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`false`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1 D1.3 and Schema 1.1.
