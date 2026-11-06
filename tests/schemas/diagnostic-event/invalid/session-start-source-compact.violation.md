# Violation: `lifetime.start_source: compact`

## Rule violated
Compaction opens no lifetime; `start_source` is one of startup, resume, fork, clear, unknown. Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`enum`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1 D1.1.
