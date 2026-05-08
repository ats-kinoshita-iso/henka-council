# Violation: change_origin out of enum (v2-specific)

## Rule violated
`change_origin` must be one of `["active", "passive"]` (R1, §6.3). The value `"spontaneous"` is not in the allowed enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§6.3, R1 — "change_origin" encodes whether a change was deliberately initiated (active / henkoten) or emerged unbidden (passive / henkaten strict sense). Only these two values are permitted.
