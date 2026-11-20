# Violation: missing required field `kind`

## Rule violated
`kind` is listed under the schema's `required`. Otherwise `valid/run-event.json` (a schema 1.0
run event, which carries no `lifetime`), so no other rule fires.

## Expected jsonschema error keyword
`required`

## Fails only on this keyword
yes

## Spec section
ADR-0006 (cloud-catcher): every event names what it measures.
