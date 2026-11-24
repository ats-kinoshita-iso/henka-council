# Phase 2 Spec (with historical mentions of a retired workstream)

YAML is canonical (ADR-0008). For posterity, this spec documents that the
Sprint 9 cmpx writer is **deprecated for cutover** and retained only as an
in-memory debugging aid; the cmpx parser refactor direction was killed by
ADR 0008.

These are *historical* references — the kind a real spec accumulates. The
direction gate must NOT block sanctioned mainline work just because the spec's
narrative names a retired workstream (the false-positive trap found during
bay-o-net adoption). Killed-workstream detection is scoped to the proposed
*contract*, not the spec's history.

## Workstreams (active)

- YAML writer + loader + canonical-form hashing.
