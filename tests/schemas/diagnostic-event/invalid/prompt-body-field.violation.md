# Violation: additional property `prompt`

## Rule violated
`diagnostic-event.schema.json` sets `additionalProperties: false`; there is no field for prompt or response bodies by design.

## Expected jsonschema error keyword
`additionalProperties`

## Spec section
ADR-0006 (cloud-catcher) §Privacy: no prompt or response bodies in any event.
