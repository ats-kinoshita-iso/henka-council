# Violation: sprint-prebrief `rationale` below `minLength`

## Rule violated

`rationale` must be at least 40 characters (`minLength: 40`). This fixture's
`rationale` is `"well-trodden"` (12 characters), which validated under the
previous `minLength: 1` but is now rejected.

## Expected jsonschema error keyword

`minLength`

## Spec section

ADR-0003 (Cynefin classification) and the #9 follow-up. The schema and the
instruction (`instructions/sprint-prebrief.md`, `skills/council-autorun`
Step 1A.6) both describe `rationale` as "one paragraph", but the prior
`minLength: 1` accepted a single character. The tightened bound rejects
placeholder rationales while staying well below a genuine one-paragraph
rationale (the valid fixtures are 250+ characters).
