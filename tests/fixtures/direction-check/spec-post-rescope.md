# Phase 2 Spec (POST-RESCOPE — bay-o-net state after ADR 0008, 2026-05-20)

YAML is the canonical persistence format per ADR-0008. Persistence work lives in
`src/comeai_extraction/persistence/`.

## Workstreams

- YAML schema design (Pydantic v2 models).
- YAML loader: `persistence.load_yaml(path) -> AuthoringModel`.
- YAML writer: `persistence.write_yaml(model, path)` with canonical-form output.

Note: the "YAML writer" here is the SANCTIONED direction. A naive keyword gate
that blocked on the bare word "writer" would false-positive on this legitimate
work — which is exactly why the killed-workstream list targets the specific
retired AgenaRisk-export workstream, not the bare word "writer".
