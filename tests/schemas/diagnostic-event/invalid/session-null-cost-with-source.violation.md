# Violation: a null cost with a cost source

## Rule violated
When `cost_usd` is null, `cost_source` is null too. Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`type`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1 Schema 1.1 (cost rules).
