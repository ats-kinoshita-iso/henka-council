# Violation: taxonomy-version-wrong-enum

## Rule violated
`governance.taxonomy_version` must equal `"2.0"` (enum with single allowed value).
This fixture sets `taxonomy_version: "1.0"`, which is not in the enum.

## Expected jsonschema error keyword
`enum`

## Spec section
§11.10 integration-signal schema — taxonomy_version enum constraint requiring "2.0" per §11.10.
