# Violation: session `event_id` that is not a UUIDv5

## Rule violated
A session event's `event_id` is UUIDv5 in namespace 5f0c2b8e-2a7d-4d38-9a51-1c2f1d6e2006 over 'session-lifetime|<session_id>|<anchor>'; this one is a version-4 UUID. Otherwise a valid schema 1.1 session event.

## Expected jsonschema error keyword
`pattern`

## Fails only on this keyword
yes

## Spec section
ADR-0006 A1 D1.5.
