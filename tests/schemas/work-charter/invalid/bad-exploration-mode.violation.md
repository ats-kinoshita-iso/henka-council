# Violation: exploration_mode out of enum

## Rule violated
`exploration_mode` must be one of `["mainline", "parallel-exploration", "competitive"]`. The value `"skunkworks"` is not in the allowed enum.

## Expected jsonschema error keyword
`enum`

## Spec section
The exploration_mode is the single declared flag that distinguishes sanctioned mainline work from deliberate parallel/competitive divergence. Only the three enumerated modes are valid.
