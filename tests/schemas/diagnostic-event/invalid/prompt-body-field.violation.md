# Violation: additional property `prompt`

## Rule violated
`diagnostic-event.schema.json` sets `additionalProperties: false`; there is no field for prompt or response bodies by design. Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`additionalProperties`

## Fails only on this keyword
yes

## Spec section
ADR-0006 (cloud-catcher) decision 5: no prompt or response bodies in any event.
