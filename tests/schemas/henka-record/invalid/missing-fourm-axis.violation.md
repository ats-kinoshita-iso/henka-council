# Violation: missing-fourm-axis.json

## Rule violated
The `henka-record` schema requires `fourM_axis` as part of its required fields (v2 R8). This fixture omits the `fourM_axis` field entirely.

## Expected jsonschema error keyword
`required`

## Spec section
§11.3 v2 R8 — `henka-record.schema.json` v2 revision adds `fourM_axis` (enum: Man/Machine/Material/Method) as a required field. The 4M taxonomy is the primary classification lens for all henkaten records per §6.
