# Violation: reversibility out of enum (v2-specific)

## Rule violated
`reversibility` must be one of `["reversible", "irreversible"]` (R9, §11.4). The value `"reversible-ish"` is not in the allowed enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.4, R9 — The reversibility field uses a strict binary enum. Only "reversible" and "irreversible" are valid values — fuzzy qualifiers like "reversible-ish" are not permitted.
