# Violation: missing required field `kind`

## Rule violated
`kind` is listed under the schema's `required`. Without it the event is not a session event either, so its `lifetime` also trips the `not` rule; the documented reason is the missing field.

## Expected jsonschema error keyword
`required`

## Spec section
ADR-0006 (cloud-catcher): every event names what it measures.
