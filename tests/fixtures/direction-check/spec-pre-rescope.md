# Phase 2 Spec (PRE-RESCOPE — reconstructed bay-o-net state, 2026-05-13)

This is the harness spec as it stood BEFORE ADR 0008 rescoped Phase 2. It is the
artifact that disagreed with the strategic anchor (docs/divorce-spec.md, which
said "bespoke schema; no writer at any point").

## Workstreams

- Workstream C: build a `.cmpx` writer that round-trips the in-memory model back
  to AgenaRisk `.cmpx`.
- Workstream D: cmpx parser refactor to support the writer's round-trip identity
  tests.

This spec is what drove Sprint 9 to ship a cmpx writer against the anchor.
