# Violation: loop_shapes[] entry missing required `status` field

## Rule violated

Each entry in the `loop_shapes[]` array must include `status` (one of
`"candidate"`, `"ratified"`, or `"deprecated"`) per the schema. This
fixture's loop-shape entry omits `status` entirely, which violates the
schema's `required` constraint on `loop_shapes[]` items.

## Expected jsonschema error keyword

`required`

## Spec section

PR-C of the Sangen Option A integration plan, ADR-0005. `status` is the
load-bearing lifecycle field that distinguishes a candidate (proposed
but not yet through the nemawashi walkthrough) from a ratified entry
(approved via Stage 4) from a deprecated entry (retired but kept for
audit traceability). Without `status`, downstream tooling and reviewers
cannot tell whether the entry is authoritative or under consideration.

See `docs/design/adr-0005-loop-shape-pattern-category.md` for the full
design rationale.
