# Violation: approval_id does not match required pattern

## Rule violated
`approval_id` must match the pattern `^APPR-[0-9]{4,}$`. The value `"APR-1"` fails because: (a) the prefix is `APR` instead of `APPR`, and (b) there are fewer than 4 digits.

## Expected jsonschema error keyword
`pattern`

## Spec section
§11.7 — approval_id uses the format APPR-NNNN (minimum 4 digits) for consistent indexing.
