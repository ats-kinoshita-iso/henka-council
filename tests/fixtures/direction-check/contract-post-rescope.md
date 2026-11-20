# Sprint 13 Contract (POST-RESCOPE)

## What I Will Build

A YAML writer `persistence.write_yaml(model, path)` producing canonical-form YAML
(sorted keys + repr-precision floats) with a content-addressable SHA-256 hash.

Aligned with the strategic anchor docs/divorce-spec.md and ADR-0008 (YAML is the
canonical persistence format).

## Success Criteria

1. `write_yaml` round-trips through `load_yaml` with byte-fidelity on frozen CPTs.
