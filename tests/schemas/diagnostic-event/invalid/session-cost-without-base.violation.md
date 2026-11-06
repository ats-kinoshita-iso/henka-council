# Violation: a cost with an unknown restored base

## Rule violated
`cost_usd` is null exactly when `lifetime.cum_cost_start_usd` (the restored base) is unknown; here the base is null and the cost a number. Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`type`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1 D1.3 and Schema 1.1 (cost rules).
