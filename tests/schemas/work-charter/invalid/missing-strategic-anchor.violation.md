# Violation: missing required strategic_anchor

## Rule violated
A work charter MUST declare the `strategic_anchor` it is reconciled against — drift from the anchor is the failure this mechanism exists to catch. The charter omits the required `strategic_anchor` property.

## Expected jsonschema error keyword
`required`

## Spec section
Without a cited strategic anchor there is nothing to check direction against; the field is required.
