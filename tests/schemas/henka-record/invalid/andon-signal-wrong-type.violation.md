# Violation: andon_signal.type out of enum

## Rule violated
`andon_signal.type` must be one of `["alert", "stop"]` (R2, §7.0.1). The value `"warning"` is not in the allowed enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§7.0.1, R2 — The andon signal type distinguishes recoverable alerts (bounded by takt time) from committed halts requiring user resume. Only `alert` and `stop` are valid signal types.
