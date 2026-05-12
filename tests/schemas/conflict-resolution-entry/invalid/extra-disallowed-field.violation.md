# Violation: extra-disallowed-field

## Rule violated
The schema sets `additionalProperties: false`. This fixture includes `undocumented_field`,
which is not listed in the schema's `properties` and is therefore disallowed.

## Expected jsonschema error keyword
`additionalProperties`

## Spec section
§11.8 conflict-resolution-entry schema — `additionalProperties: false` constraint.
