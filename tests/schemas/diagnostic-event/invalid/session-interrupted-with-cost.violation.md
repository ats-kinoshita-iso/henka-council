# Violation: an interrupted lifetime with a cost

## Rule violated
An interrupted lifetime (no closing cost-state) has `cost_usd: null`; no estimate is written. Otherwise a valid schema 1.1 interrupted session event.

## Expected jsonschema error keyword
`type`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1 D1.6 and D3.
