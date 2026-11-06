# Violation: `source` outside the producer enum

## Rule violated
`source` must be one of the known producers (claude-code-session, auto-mate, trine-eval, henkaten-council, archivist, otel). Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`enum`

## Fails only on this keyword
yes

## Spec section
ADR-0006 (cloud-catcher): one event schema, known producers.
