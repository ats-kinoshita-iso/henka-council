# Violation: cynefin label out of enum

## Rule violated

`cynefin` must be one of `["clear", "complicated", "complex", "chaotic"]`
per `schemas/sprint-prebrief.schema.json`. The value `"easy"` is not in
the allowed enum.

## Expected jsonschema error keyword

`enum`

## Spec section

ADR-0003. The four Cynefin labels are the entire vocabulary for prospective
sprint classification; allowing free-form labels would defeat the audit
discipline this artefact exists to support. See
`instructions/sprint-prebrief.md` for the rubric describing what each
valid label means.
