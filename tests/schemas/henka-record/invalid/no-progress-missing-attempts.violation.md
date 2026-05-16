# Violation: no-progress response_type without required attempts[]

## Rule violated

When `response_type` is `"no-progress"`, the schema requires `attempts` to
be present and contain at least one entry (the agent must enumerate what
it tried before judging that it could not advance). This record sets
`response_type: "no-progress"` but omits `attempts` entirely.

## Expected jsonschema error keyword

`required` (from the schema's top-level `allOf` → `if/then` clause)

## Spec section

PR-B of the Sangen Option A integration plan, ADR-0004. The non-empty
`attempts[]` array is the audit-data encoding of the agent's
metacognition: without it, `no-progress` cannot be distinguished in audit
data from a content-free halt. This is the load-bearing constraint that
makes `no-progress` a meaningfully different termination form from
`andon-stop` and `resource-cap`. See
`instructions/stop-conditions.md` and
`docs/design/adr-0004-stop-conditions.md` for the full rationale.
