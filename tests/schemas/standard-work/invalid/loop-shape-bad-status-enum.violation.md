# Violation: loop_shapes[] entry has an out-of-enum `status`

## Rule violated

`loop_shapes[].status` must be one of `"candidate"`, `"ratified"`, or
`"deprecated"`. This fixture sets `status: "approved"` — a plausible-looking
typo that is not a member of the enum.

## Expected jsonschema error keyword

`enum`

## Spec section

ADR-0005 and the #9 follow-up (negative-coverage gap: the prior suite only
exercised "missing status", not "wrong status"). Lifecycle tooling branches on
the exact enum value, so a near-miss like `"approved"` / `"in-progress"` must be
rejected rather than silently treated as an unknown state.
