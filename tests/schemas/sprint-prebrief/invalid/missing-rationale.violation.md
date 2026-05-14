# Violation: missing required field `rationale`

## Rule violated

`rationale` is a required field on every sprint prebrief per
`schemas/sprint-prebrief.schema.json` (also constrained to `minLength: 1`,
no empty strings). The classification's audit value depends on the
written rationale being present and non-empty.

## Expected jsonschema error keyword

`required`

## Spec section

ADR-0003. Without a written rationale, the Cynefin label is opaque to
future review — the label alone does not preserve the reasoning that
produced it. The rationale is what makes the prebrief reviewable later.
