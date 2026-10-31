# Violation: `source` outside the producer enum

## Rule violated
`source` must be one of the known producers (claude-code-session, auto-mate, trine-eval, henkaten-council, archivist, otel).

## Expected jsonschema error keyword
`enum`

## Spec section
ADR-0006 (cloud-catcher): one event schema, known producers.
