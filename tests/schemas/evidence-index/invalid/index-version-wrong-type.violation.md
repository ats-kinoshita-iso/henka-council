# Violation: index-version-wrong-type

## Rule violated
`index_version` must be a string matching the semver pattern `^[0-9]+\.[0-9]+\.[0-9]+$`.
This fixture provides an integer `100` instead of a string like `"1.0.0"`.

## Expected jsonschema error keyword
`type`

## Spec section
§11.9 evidence-index schema — index_version type and pattern constraints.
