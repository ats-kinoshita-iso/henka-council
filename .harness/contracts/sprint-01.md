# Sprint 01 Contract — D1 Schema Definitions

## Scope

Sprint 1 delivers the complete JSON Schema foundation for the henka-council plugin.
This encompasses all 11 schemas described in §11 of the product specification
(three of which carry v2 revisions and one of which is entirely new in v2), three
Python validator scripts for the highest-traffic schemas, and a full fixture suite
of valid and invalid JSON examples for every schema. The schemas are the
authoritative data contracts that all subsequent sprints depend on: agent files
(D2), append scripts (S2), hooks (S3), and end-to-end tests (S4–S6) all validate
against these artifacts. No other deliverables are in scope.

---

## Files in Scope

**Schemas (11 files):**
- `schemas/council-config.schema.json`
- `schemas/council-manifest.schema.json`
- `schemas/henka-record.schema.json` (v2 revised: R1/R2/R4/R6/R8)
- `schemas/decision-log-entry.schema.json` (v2 revised: R3/R5/R9/R10)
- `schemas/standard-work.schema.json`
- `schemas/audit-log-entry.schema.json`
- `schemas/human-approval-log-entry.schema.json`
- `schemas/conflict-resolution-entry.schema.json`
- `schemas/evidence-index.schema.json`
- `schemas/integration-signal.schema.json`
- `schemas/effective-autonomy.schema.json` (NEW v2/R10)

**Validator scripts (3 files):**
- `scripts/validate-council-config.py`
- `scripts/validate-henka-record.py`
- `scripts/validate-decision-log.py`

**Test fixtures (11 schemas × 2 directories × ≥3 files = ≥66 JSON files):**
- `tests/schemas/council-config/valid/*.json` (≥3 files)
- `tests/schemas/council-config/invalid/*.json` (≥3 files)
- `tests/schemas/council-manifest/valid/*.json` (≥3 files)
- `tests/schemas/council-manifest/invalid/*.json` (≥3 files)
- `tests/schemas/henka-record/valid/*.json` (≥3 files)
- `tests/schemas/henka-record/invalid/*.json` (≥3 files)
- `tests/schemas/decision-log-entry/valid/*.json` (≥3 files)
- `tests/schemas/decision-log-entry/invalid/*.json` (≥3 files)
- `tests/schemas/standard-work/valid/*.json` (≥3 files)
- `tests/schemas/standard-work/invalid/*.json` (≥3 files)
- `tests/schemas/audit-log-entry/valid/*.json` (≥3 files)
- `tests/schemas/audit-log-entry/invalid/*.json` (≥3 files)
- `tests/schemas/human-approval-log-entry/valid/*.json` (≥3 files)
- `tests/schemas/human-approval-log-entry/invalid/*.json` (≥3 files)
- `tests/schemas/conflict-resolution-entry/valid/*.json` (≥3 files)
- `tests/schemas/conflict-resolution-entry/invalid/*.json` (≥3 files)
- `tests/schemas/evidence-index/valid/*.json` (≥3 files)
- `tests/schemas/evidence-index/invalid/*.json` (≥3 files)
- `tests/schemas/integration-signal/valid/*.json` (≥3 files)
- `tests/schemas/integration-signal/invalid/*.json` (≥3 files)
- `tests/schemas/effective-autonomy/valid/*.json` (≥3 files)
- `tests/schemas/effective-autonomy/invalid/*.json` (≥3 files)

**Required-name fixture files (must exist with these exact filenames — referenced by SC-6 verification):**
- `tests/schemas/council-config/valid/example-01.json`
- `tests/schemas/henka-record/valid/example-01.json`
- `tests/schemas/decision-log-entry/valid/example-01.json`
- `tests/schemas/council-config/invalid/missing-required.json`
- `tests/schemas/henka-record/invalid/missing-fourm-axis.json`
- `tests/schemas/decision-log-entry/invalid/missing-reversibility.json`

**Violation sidecar files (one per invalid fixture, recognized scope element per Technical Notes convention):**
- `tests/schemas/<schema>/invalid/*.violation.md` — one sidecar per invalid JSON fixture across all 11 schema directories

---

## Success Criteria

### Deterministic (weights sum to 70%)

**SC-1 [weight: 15%] — All 11 schemas are valid JSON, valid JSON Schema draft-07, and carry the `$schema` declaration**

Input: run the JSON syntax check, schema-meta-validation, and `$schema` declaration check on every schema file.

Verification:
```
python -m json.tool schemas/council-config.schema.json
python -m json.tool schemas/council-manifest.schema.json
python -m json.tool schemas/henka-record.schema.json
python -m json.tool schemas/decision-log-entry.schema.json
python -m json.tool schemas/standard-work.schema.json
python -m json.tool schemas/audit-log-entry.schema.json
python -m json.tool schemas/human-approval-log-entry.schema.json
python -m json.tool schemas/conflict-resolution-entry.schema.json
python -m json.tool schemas/evidence-index.schema.json
python -m json.tool schemas/integration-signal.schema.json
python -m json.tool schemas/effective-autonomy.schema.json
```
Note: the glob form `python -m json.tool schemas/*.schema.json` from spec §5 is illustrative; the 11 separate calls above are the canonical verification (Python's `json.tool` only reliably handles one file at a time).

For draft-07 meta-validity:
```
python -c "import jsonschema, json; [jsonschema.Draft7Validator.check_schema(json.load(open(f))) for f in ['schemas/council-config.schema.json','schemas/council-manifest.schema.json','schemas/henka-record.schema.json','schemas/decision-log-entry.schema.json','schemas/standard-work.schema.json','schemas/audit-log-entry.schema.json','schemas/human-approval-log-entry.schema.json','schemas/conflict-resolution-entry.schema.json','schemas/evidence-index.schema.json','schemas/integration-signal.schema.json','schemas/effective-autonomy.schema.json']]"
```

For `$schema` declaration (all 11 must declare `http://json-schema.org/draft-07/schema#`):
```
python -c "
import json, sys
schemas = ['schemas/council-config.schema.json','schemas/council-manifest.schema.json','schemas/henka-record.schema.json','schemas/decision-log-entry.schema.json','schemas/standard-work.schema.json','schemas/audit-log-entry.schema.json','schemas/human-approval-log-entry.schema.json','schemas/conflict-resolution-entry.schema.json','schemas/evidence-index.schema.json','schemas/integration-signal.schema.json','schemas/effective-autonomy.schema.json']
errors = []
for f in schemas:
    s = json.load(open(f))
    if s.get('\$schema') != 'http://json-schema.org/draft-07/schema#':
        errors.append(f + ' missing or wrong \$schema')
if errors:
    print('FAIL:', errors); sys.exit(1)
print('ALL PASS')
"
```

Pass condition: all `python -m json.tool` calls exit 0; `check_schema` raises no exception for any of the 11 files; `$schema` check prints `ALL PASS` and exits 0.

Maps to: SC-D1-1 (§5)

---

**SC-2 [weight: 12%] — `henka-record.schema.json` contains all v2-required fields**

Input: inspect `schemas/henka-record.schema.json`.

Verification:
```
python -c "import json; s=json.load(open('schemas/henka-record.schema.json')); p=s['properties']; assert 'fourM_axis' in p and set(p['fourM_axis'].get('enum',[])) == {'Man','Machine','Material','Method'}; assert 'change_origin' in p and set(p['change_origin'].get('enum',[])) == {'active','passive'}; assert 'andon_signal' in p; assert 'yokoten' in p; yo=p['yokoten']; yp=yo.get('properties',{}); assert 'deployed_to' in yp; ev=p.get('evidence',{}); items=ev.get('items',{}); evp=items.get('properties',{}); assert 'verification' in evp; print('PASS')"
```

Pass condition: script prints `PASS` and exits 0.

Maps to: SC-D1-2 (§5, §11.3, R1/R2/R4/R6/R8)

---

**SC-3 [weight: 10%] — `decision-log-entry.schema.json` contains all v2-required fields**

Input: inspect `schemas/decision-log-entry.schema.json`.

Verification:
```
python -c "import json; s=json.load(open('schemas/decision-log-entry.schema.json')); p=s['properties']; assert 'effective_autonomy_at_decision' in p; assert 'reversibility' in p; assert 'nemawashi_walkthrough_version' in p; assert 'andon_resolution' in p; print('PASS')"
```

Pass condition: script prints `PASS` and exits 0.

Maps to: SC-D1-3 (§5, §11.4, R3/R5/R9/R10)

---

**SC-4 [weight: 8%] — `effective-autonomy.schema.json` exists and contains required fields**

Input: inspect `schemas/effective-autonomy.schema.json`.

Verification:
```
python -c "import json; s=json.load(open('schemas/effective-autonomy.schema.json')); req=s.get('required',[]); p=s['properties']; assert 'level' in req; assert 'last_change' in req; assert 'reason' in req; assert p['level'].get('type')=='integer'; assert p['level'].get('minimum')==0; assert p['level'].get('maximum')==5; assert 'restored_when' in p; assert 'trigger_history' in p and p['trigger_history'].get('type')=='array'; print('PASS')"
```

Pass condition: script prints `PASS` and exits 0.

Maps to: SC-D1-4 (§5, §11.11, NEW v2/R10)

---

**SC-5 [weight: 15%] — All 11 schemas have ≥3 valid and ≥3 invalid fixtures; valid fixtures validate; invalid fixtures fail**

Input: for each schema, check fixture file counts, then run each fixture through the appropriate validator.

Verification: run the following single self-contained command. It checks all 22 fixture directories, validates every valid fixture against its schema, and asserts every invalid fixture fails validation. `uv run python` or `python` both work on Windows PowerShell and POSIX Bash.

```
python -c "
import glob, json, sys, subprocess, pathlib
import jsonschema

DEDICATED = {
    'council-config':     ('scripts/validate-council-config.py', None),
    'henka-record':       ('scripts/validate-henka-record.py',   None),
    'decision-log-entry': ('scripts/validate-decision-log.py',   None),
}
GENERIC = [
    'council-manifest', 'standard-work', 'audit-log-entry',
    'human-approval-log-entry', 'conflict-resolution-entry',
    'evidence-index', 'integration-signal', 'effective-autonomy',
]
ALL_SCHEMAS = list(DEDICATED.keys()) + GENERIC
errors = []

def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))

for schema_name in ALL_SCHEMAS:
    for kind in ('valid', 'invalid'):
        pattern = f'tests/schemas/{schema_name}/{kind}/*.json'
        files = glob.glob(pattern)
        if len(files) < 3:
            errors.append(f'{pattern}: expected >=3 files, got {len(files)}')

for schema_name, (script, _) in DEDICATED.items():
    for f in glob.glob(f'tests/schemas/{schema_name}/valid/*.json'):
        r = subprocess.run(['python', script, f], capture_output=True)
        if r.returncode != 0:
            errors.append(f'VALID fixture failed: {f} (exit {r.returncode})')
    for f in glob.glob(f'tests/schemas/{schema_name}/invalid/*.json'):
        r = subprocess.run(['python', script, f], capture_output=True)
        if r.returncode == 0:
            errors.append(f'INVALID fixture unexpectedly passed: {f}')

for schema_name in GENERIC:
    schema_doc = load(f'schemas/{schema_name}.schema.json')
    for f in glob.glob(f'tests/schemas/{schema_name}/valid/*.json'):
        try:
            jsonschema.validate(load(f), schema_doc)
        except jsonschema.ValidationError as e:
            errors.append(f'VALID fixture failed: {f}: {e.message}')
    for f in glob.glob(f'tests/schemas/{schema_name}/invalid/*.json'):
        try:
            jsonschema.validate(load(f), schema_doc)
            errors.append(f'INVALID fixture unexpectedly passed: {f}')
        except jsonschema.ValidationError:
            pass  # expected

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: the command exits 0 and prints `ALL PASS`. Any file-count shortfall or validation mismatch causes a non-zero exit and prints the specific failures.

Maps to: SC-D1-5 (§5, §15.5, v2.1 amendment A8)

---

**SC-6 [weight: 10%] — `scripts/validate-council-config.py`, `scripts/validate-henka-record.py`, and `scripts/validate-decision-log.py` exist, accept a file path argument, exit 0 on valid input, and exit non-zero on invalid input**

Input: run each script against a known-valid and a known-invalid fixture.

Verification:
```
python scripts/validate-council-config.py tests/schemas/council-config/valid/example-01.json
python scripts/validate-henka-record.py tests/schemas/henka-record/valid/example-01.json
python scripts/validate-decision-log.py tests/schemas/decision-log-entry/valid/example-01.json
```
All must exit 0.
```
python scripts/validate-council-config.py tests/schemas/council-config/invalid/missing-required.json
python scripts/validate-henka-record.py tests/schemas/henka-record/invalid/missing-fourm-axis.json
python scripts/validate-decision-log.py tests/schemas/decision-log-entry/invalid/missing-reversibility.json
```
All must exit non-zero.

Pass condition: exit codes match expectations for all six invocations.

Maps to: SC-D1-5 partial (§5)

Note: SC-D1-6 (which tests `scripts/append-henka.py` and `scripts/append-decision.py` for append-on-invalid-schema rejection) is deferred to Sprint 4, where those scripts are deliverables. It is NOT evaluated here.

---

### LLM-as-judge (weights sum to 30%)

**SC-7 [weight: 15%] — Semantic correctness of v2-revised fields in `henka-record.schema.json` and `decision-log-entry.schema.json`**

Rubric dimensions:
1. `fourM_axis` enum matches the 4M taxonomy exactly: `Man`, `Machine`, `Material`, `Method` — no extras, no omissions (§6, R8).
2. `change_origin` enum is exactly `["active", "passive"]` and the schema description conveys that `active` = deliberately initiated (henkoten) and `passive` = emerged unbidden (henkaten strict sense) (§6.3, R1).
3. `andon_signal` block contains sub-fields `type` (enum `["alert", "stop"]`), `reason` (string), `evidence` (array), and `swarm_request` (array) consistent with §7.0.1 (R2).
4. `verification` inside evidence items is a string with a description or pattern that references the allowlist intent from §4.5 (R4).
5. `yokoten` block contains `applicable_to_subsequent_sprints` (array of sprint identifiers or `"all"`), `adaptation_notes` (string), and `deployed_to` (array) as specified in §11.3 (R6).
6. `decision-log-entry.schema.json` — `reversibility` field uses an enum of `["reversible", "irreversible"]`; `effective_autonomy_at_decision` is an integer 0–5; `nemawashi_walkthrough_version` is nullable string; `andon_resolution` captures resolution outcome (§11.4, R3/R5/R9/R10).

Score: PASS if ≥5 of 6 dimensions are fully satisfied; PARTIAL (50% weight credit) if 3–4 satisfied; FAIL if ≤2 satisfied.

---

**SC-8 [weight: 10%] — Invalid fixture violations are meaningful, documented, and diverse**

Rubric dimensions:
1. Each `invalid/` fixture directory contains fixtures that exercise at least three distinct violation classes (e.g. missing required field, wrong type, enum out of range, extra disallowed field, wrong array item shape). A directory where all three fixtures have the same violation type fails this dimension.
2. Each invalid fixture file is accompanied by either (a) a `*.violation.md` sidecar file (the canonical convention per Technical Notes) or (b) a `violations-index.md` file in the `invalid/` directory listing all fixtures with their violation types and expected `jsonschema` error keywords. The documentation must be human-readable and accurate. A `_comment` JSON key inside the fixture is NOT an acceptable substitute (JSON has no standard comment syntax, and a `_comment` key may itself constitute an unintended schema violation).
3. The invalid fixtures for the two v2-revised schemas (`henka-record` and `decision-log-entry`) specifically include at least one fixture that exercises a v2-specific field violation (e.g. missing `fourM_axis`, invalid `change_origin` value, missing `reversibility`).

Score: PASS if all three dimensions are satisfied across all 11 schema invalid-fixture directories; PARTIAL (50% credit) if ≥8 of 11 directories fully satisfy all three dimensions; FAIL otherwise.

---

**SC-9 [weight: 5%] — `integration-signal.schema.json` correctly models the governance signal structure and `effective-autonomy.schema.json` trigger history semantics**

Rubric dimensions:
1. `integration-signal.schema.json` includes a `taxonomy_version` field (string, expected value `"2.0"`) and a `governance` object with sub-fields `enabled` (boolean), `plugin` (string), `council_state_path` (string), and `council_state_path` resolving to the `.council/` directory (§11.10, §10.2).
2. `effective-autonomy.schema.json` — `trigger_history` array items have a defined `items` schema (not just `type: array`) that captures at minimum: `trigger_type` (string or enum), `timestamp` (date-time), and `from_level` / `to_level` integers. The schema is specific enough that a generic `{}` item would fail validation.

Score: PASS if both dimensions satisfied; PARTIAL (50% credit) if one dimension satisfied; FAIL if neither satisfied.

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

- MUST NOT modify any `.harness/*` files other than those explicitly authorized by the Evaluator for this sprint. The harness files (`.harness/spec.md`, `.harness/sprints.json`, `.harness/sprint-state.json`, `.harness/progress.md`, `.harness/config.json`) are read-only inputs for this sprint.
- MUST NOT create files outside the "Files in Scope" list above (including the "Required-name fixture files" and "Violation sidecar files" subsections). In particular, no agent files (`agents/`), skill files (`skills/`), hook files (`hooks/`), instruction files (`instructions/`), or template files (`templates/`) may be created in this sprint. Violation sidecar files (`tests/schemas/<schema>/invalid/*.violation.md`) are explicitly in scope and may be created freely.
- MUST NOT omit `tests/schemas/<schema>/valid/` or `tests/schemas/<schema>/invalid/` directories for any of the 11 schemas. All 22 fixture directories are required.
- MUST NOT place `verification` string values in fixture JSON files that violate the v2.1 allowlist from §4.5. Specifically: any JSON fixture file that contains a `verification` key must have its value drawn only from allowlisted prefixes (`git diff…`, `grep…`, `cat…`, `jq…`, `python -m json.tool…`, `python scripts/validate-*.py…`, `test…`). Note: schema `description` prose in `.schema.json` files (e.g. `"description": "A re-runnable command such as git log…"`) is documentation, not an executable verification string, and is NOT subject to the §4.5 allowlist gate. Only the `verification` key's actual string value inside fixture JSON files is gated.
- MUST NOT ship schemas that reference each other via `$ref` to relative paths that do not exist in this sprint's file-scope list. Cross-schema references are permitted only to other schemas in the `schemas/` directory created in this sprint.
- MUST NOT implement any logic in `scripts/validate-*.py` beyond: (a) accepting a file path argument, (b) loading the JSON, (c) validating against the corresponding schema, (d) printing a human-readable error message, and (e) exiting with code 0 (valid) or non-zero (invalid). The append scripts (`append-henka.py`, `append-decision.py`) are out of scope for this sprint and must NOT be created here.
- MUST NOT ship a schema that lacks the `"$schema": "http://json-schema.org/draft-07/schema#"` declaration. All 11 schema files must carry this exact declaration as a top-level key.
- MUST NOT define the following v2-required properties in `henka-record.schema.json` via `$ref` indirection: `fourM_axis`, `change_origin`, `andon_signal`, `evidence` (and its `items` sub-schema), `yokoten`. All of these properties must be defined inline in the `properties` object, not as `{"$ref": "..."}` pointers. Likewise, the following properties in `decision-log-entry.schema.json` must be defined inline (no `$ref`): `reversibility`, `effective_autonomy_at_decision`, `nemawashi_walkthrough_version`, `andon_resolution`. This ensures SC-2 and SC-3 verification one-liners work correctly without `$ref` resolution.

---

## Reference Solutions

Reference shape for **SC-7** (highest-weighted LLM-judge criterion) — illustrative field blocks for `henka-record.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "henka-record.schema.json",
  "title": "HenkaRecord",
  "type": "object",
  "required": ["id", "timestamp", "fourM_axis", "change_origin", "sub_type", "impact_level", "description"],
  "properties": {
    "fourM_axis": {
      "type": "string",
      "enum": ["Man", "Machine", "Material", "Method"],
      "description": "Primary 4M classification axis for this change point."
    },
    "change_origin": {
      "type": "string",
      "enum": ["active", "passive"],
      "description": "active = deliberately initiated (henkoten); passive = emerged unbidden (henkaten strict sense). Passive changes default to lower confidence/impact unless corroborated by a second signal."
    },
    "andon_signal": {
      "type": "object",
      "properties": {
        "type": { "type": "string", "enum": ["alert", "stop"] },
        "reason": { "type": "string" },
        "evidence": { "type": "array", "items": { "type": "string" } },
        "swarm_request": { "type": "array", "items": { "type": "string" } }
      },
      "required": ["type", "reason"]
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "evidence_class": { "type": "string", "enum": ["observed", "inferred", "speculative"] },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
          "verification": {
            "type": "string",
            "description": "A re-runnable command conformant with the §4.5 verification syntax allowlist (e.g. 'git log --oneline -5', 'grep -r pattern src/', 'cat file.json | jq .field'). Required when evidence_class is 'observed'."
          }
        },
        "required": ["evidence_class", "confidence"]
      }
    },
    "yokoten": {
      "type": "object",
      "properties": {
        "applicable_to_subsequent_sprints": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Sprint identifiers this learning applies to, or ['all'] for all remaining sprints."
        },
        "adaptation_notes": { "type": "string" },
        "deployed_to": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

---

## Out of Scope

- **Agent contracts (D2 — Sprint 2):** no `agents/*.md` files, no `instructions/*.md` files, no `templates/*.md` or `templates/*.json` files (other than schemas).
- **Append scripts (S2 — Sprint 4):** `scripts/append-henka.py` and `scripts/append-decision.py` are explicitly D2/S2 deliverables. Do not create them here.
- **Remaining validator scripts (S2):** `scripts/compute-evidence-class.py`, `scripts/update-effective-autonomy.py`, `scripts/run-verification.py`, `scripts/rotate-audit-log.py` are not in this sprint.
- **Skill files (S1+ — Sprints 3–8):** no `skills/*/SKILL.md` files.
- **Hook files (S3 — Sprint 5):** no `hooks/` files.
- **Plugin metadata (S1 — Sprint 3):** `.claude-plugin/plugin.json`, `.mcp.json`, `.claude/settings.json`, `README.md`, `LICENSE`, `CLAUDE.md` are Sprint 3 deliverables.
- **End-to-end fixture project (S4 — Sprint 6):** `tests/fixtures/dummy-project/` is out of scope.
- **Everything listed in §15 "Out of v0.1":** Archaeologist agent, Prompt Forge agent, parallel dispatch default, MCP-based git server, `evaluator-bias-change` sub-type, direct jishuken-to-standard-work promotion, CC-001 default-on, `pass@k`/`pass^k` metrics.
- **Full schema coverage for 8 non-validated schemas:** the three `validate-*.py` scripts cover `council-config`, `henka-record`, and `decision-log-entry`. The remaining 8 schemas (`standard-work`, `audit-log-entry`, `human-approval-log-entry`, `conflict-resolution-entry`, `evidence-index`, `integration-signal`, `council-manifest`, `effective-autonomy`) are validated only via `jsonschema` one-liners in the fixture tests — no dedicated scripts required for those 8 schemas in this sprint.

---

## Technical Notes

**JSON Schema draft version:** All schemas MUST declare `"$schema": "http://json-schema.org/draft-07/schema#"`. The `jsonschema` Python package's `Draft7Validator` is the reference implementation. Draft-07 is required because later sprints' hooks and scripts will use `jsonschema` with the `Draft7Validator` class directly.

**The 11 schemas verbatim from spec §11:**
1. `council-config.schema.json` (§11.1)
2. `council-manifest.schema.json` (§11.2)
3. `henka-record.schema.json` (§11.3, REVISED v2)
4. `decision-log-entry.schema.json` (§11.4, REVISED v2)
5. `standard-work.schema.json` (§11.5)
6. `audit-log-entry.schema.json` (§11.6)
7. `human-approval-log-entry.schema.json` (§11.7)
8. `conflict-resolution-entry.schema.json` (§11.8)
9. `evidence-index.schema.json` (§11.9)
10. `integration-signal.schema.json` (§11.10)
11. `effective-autonomy.schema.json` (§11.11, NEW v2)

**v2 revisions checklist (fields that MUST appear in schemas):**
- R1 — `henka-record`: `change_origin` enum `["active", "passive"]`
- R2 — `henka-record`: `andon_signal` block with `type`, `reason`, `evidence[]`, `swarm_request[]`
- R3 — `decision-log-entry`: `andon_resolution` field
- R4 — `henka-record` evidence items: `verification` string field
- R5 — `decision-log-entry`: `nemawashi_walkthrough_version` (nullable string)
- R6 — `henka-record`: `yokoten` block with `applicable_to_subsequent_sprints`, `adaptation_notes`, `deployed_to[]`
- R8 — `henka-record`: `fourM_axis` enum `["Man", "Machine", "Material", "Method"]`
- R9 — `decision-log-entry`: `reversibility` enum `["reversible", "irreversible"]`
- R10 — `decision-log-entry`: `effective_autonomy_at_decision` integer 0–5; `effective-autonomy.schema.json` NEW

**Validator script scope decision:** `sprints.json` lists three validator scripts — `validate-council-config.py`, `validate-henka-record.py`, `validate-decision-log.py`. Per spec §5 SC-D1-5, fixture tests for all 11 schemas must confirm valid fixtures pass and invalid fixtures fail the "corresponding `scripts/validate-*.py`." However, only three dedicated scripts are in scope; the phrase "corresponding" is satisfied for the eight remaining schemas by using `jsonschema` CLI invocations (via Python one-liners) in acceptance testing rather than dedicated per-schema scripts. This reading is recorded here so the Evaluator can override it if they require dedicated scripts for all 11.

**Cross-platform path concerns:** All Python scripts must use `pathlib.Path` and accept both POSIX and Windows paths. Fixture file names must use lowercase with hyphens (no spaces, no underscores preferred) to avoid cross-platform glob issues. Schema `$id` values must use forward-slash paths regardless of host OS.

**Invalid fixture documentation convention:** Each `invalid/` fixture file must be accompanied by a `*.violation.md` sidecar (e.g. `missing-fourm-axis.violation.md`) documenting: (a) the rule violated, (b) the expected `jsonschema` error message or keyword, and (c) the spec section that mandates the rule. These sidecar files are **explicitly listed in "Files in Scope"** under the "Violation sidecar files" subsection, so the Should-NOT gate against out-of-scope files does not conflict with producing them. Alternatively, a single `violations-index.md` per `invalid/` directory may substitute (see SC-8 dimension 2).

**`integration-signal.schema.json` note:** This schema models the `governance` key written by `/council-kickoff` to `.harness/config.json`. The `taxonomy_version` field must default to or require `"2.0"` per §11.10. The schema does not enforce the full `.harness/config.json` structure — only the `governance` sub-object shape.

**`effective-autonomy.schema.json` note:** `trigger_history` array items must have a defined `items` sub-schema (not a bare array) so that later `scripts/update-effective-autonomy.py` (Sprint 4) can rely on schema validation to enforce trigger record shape. At minimum each trigger-history item should require `trigger_type`, `timestamp`, `from_level`, and `to_level`.

**`jsonschema` package dependency:** the three `validate-*.py` scripts must work with `jsonschema` ≥ 4.0 (the version available via `uv run python`). They should not hard-code a specific minor version.

---

## Evaluator Review

**Reviewer:** Evaluator subagent
**Date:** 2026-05-07
**Status: NEEDS REVISION**

### Findings

**Finding 1**
- Severity: BLOCKER
- Category: Completeness / Testability
- Description: SC-6 maps to "SC-D1-6 partial (§5)" but the spec's SC-D1-6 tests `scripts/append-henka.py` and `scripts/append-decision.py`, which are explicitly out of scope for Sprint 1 (they are Sprint 4 / S2 deliverables). The contract cannot partially satisfy a spec criterion that requires out-of-scope artifacts. If an Evaluator grades SC-6 against the spec's SC-D1-6 text verbatim, it will auto-fail because neither append script is produced in this sprint. The "Maps to" annotation is misleading and will cause grading ambiguity.
- Recommended fix: Change SC-6's "Maps to" line to read "Maps to: SC-D1-5 partial (§5)" only. Remove the SC-D1-6 reference entirely and add an explicit note that SC-D1-6 (append script rejection) is deferred to Sprint 4 and will be evaluated there. This does not require adding any new success criterion; it just corrects the mapping attribution.

**Finding 2**
- Severity: BLOCKER
- Category: Testability
- Description: SC-5's "Full pass condition" uses `ls tests/schemas/<schema>/valid/*.json | wc -l` — this is POSIX shell syntax. This project's stated platform is Windows (PowerShell), and the working directory is a Windows path. The verification command as written will fail on the target platform, making SC-5's deterministic pass condition untestable without platform substitution. A 15%-weight criterion cannot have a broken pass condition.
- Recommended fix: Replace the `ls ... | wc -l` idiom with a cross-platform Python one-liner: `python -c "import glob; files=glob.glob('tests/schemas/council-config/valid/*.json'); assert len(files) >= 3, f'expected >=3, got {len(files)}'"` — and provide this command for all 11 schema directories (or a loop form that covers all 11 in one invocation). Alternatively, provide a single `python -c` expression that checks all 22 directories in one pass, which both platforms can run via `uv run python`.

**Finding 3**
- Severity: MAJOR
- Category: Testability
- Description: SC-6 hard-codes specific invalid fixture filenames: `tests/schemas/henka-record/invalid/missing-fourm-axis.json` and `tests/schemas/decision-log-entry/invalid/missing-reversibility.json`. These filenames are not listed in "Files in Scope" (which only specifies `invalid/*.json`). If the Generator names files differently (e.g. `no-fourm-axis.json`, `invalid-fourm-axis.json`, or uses hyphens consistently as specified in Technical Notes under cross-platform path concerns), SC-6's verification will fail with a FileNotFoundError even though the criterion's spirit is met. The same risk applies to `tests/schemas/council-config/invalid/missing-required.json` (referenced in both SC-5 and SC-6).
- Recommended fix: Either (a) add these three specific filenames to the "Files in Scope" list so the Generator is contractually required to use them, or (b) rewrite the SC-6 invalid-path checks to discover the first file matching `invalid/*.json` rather than using a hardcoded name: `python -c "import glob; f=glob.glob('tests/schemas/henka-record/invalid/*.json')[0]; import subprocess; r=subprocess.run(['python','scripts/validate-henka-record.py',f]); assert r.returncode != 0"`. Option (a) is simpler and more predictable.

**Finding 4**
- Severity: MAJOR
- Category: Testability
- Description: SC-5 is explicitly marked "illustrative" for 8 of 11 schemas. At 15% weight, this is tied for the highest-weight deterministic criterion, but the verification is incomplete — it shows one example for the three dedicated-validator schemas and one example for one of the eight remaining schemas. The Evaluator is left to independently generate and run 20+ additional commands. A deterministic criterion at this weight must provide either (a) a complete runnable command that checks all 11 schemas in one invocation, or (b) an exhaustive list of per-schema commands. "Analogous for the remaining eight" is not a pass condition an Evaluator can mechanically execute.
- Recommended fix: Provide a single Python script or one-liner that loops over all 11 schema directories, checks fixture counts (≥3 valid, ≥3 invalid), and runs all fixtures through the appropriate validator (dedicated script for 3, jsonschema one-liner for 8). For example: `python -c "import glob, subprocess, sys, json, jsonschema; schemas=[...]; [check(s) for s in schemas]; print('ALL PASS')"`. This makes SC-5 a single command the Evaluator can run and get a binary exit code.

**Finding 5**
- Severity: MAJOR
- Category: Testability
- Description: SC-2's verification one-liner will raise a `KeyError` or produce a false PASS if `henka-record.schema.json` defines fields via `$ref` rather than inline `properties`. The chain `p['fourM_axis'].get('enum', [])` assumes `fourM_axis` is an inline object with an `enum` key. A `{"$ref": "#/definitions/fourMAxis"}` value has no `get('enum', [])` — it would silently return `[]`, and `set([]) == {'Man', 'Machine', 'Material', 'Method'}` is False, causing a misleading FAIL. Conversely, the `ev.get('items', {}).get('properties', {})` chain would return `{}` if `evidence.items` is a `$ref`, causing a false FAIL on a valid implementation. The verification must handle `$ref`-based definitions.
- Recommended fix: Either (a) add a constraint to the contract that the Generator MUST define all v2-required fields inline (no `$ref` for these properties), which is reasonable given the schema simplicity, or (b) extend the verification to resolve `$ref` before asserting: add `jsonschema.RefResolver` handling in the one-liner, or use a simpler `grep`-based check (`grep -q '"fourM_axis"' schemas/henka-record.schema.json`) combined with a separate `jsonschema.validate` call against a known-valid fixture. Option (a) is the right call here because `$ref` for simple enum fields adds complexity with no benefit.

**Finding 6**
- Severity: MINOR
- Category: Testability
- Description: SC-1 does not verify that schemas declare `"$schema": "http://json-schema.org/draft-07/schema#"`. The Technical Notes state this is a MUST requirement, but neither `python -m json.tool` nor `Draft7Validator.check_schema()` checks for the `$schema` declaration. A schema can omit the `$schema` key entirely and still pass SC-1 while violating the Technical Notes requirement. Later sprints (S3) depend on scripts using `Draft7Validator` directly, so schemas without the declaration may silently degrade behavior.
- Recommended fix: Add one additional verification command to SC-1: `python -c "import json; schemas=[...]; [assert json.load(open(f)).get('\$schema') == 'http://json-schema.org/draft-07/schema#', f+' missing \$schema' for f in schemas]"`. Alternatively, add a Should-NOT criterion: "MUST NOT ship a schema that lacks the `\"\$schema\": \"http://json-schema.org/draft-07/schema#\"` declaration."

**Finding 7**
- Severity: MINOR
- Category: Specificity
- Description: The Should-NOT criterion "MUST NOT use a `verification` field value in any schema or fixture that fails the v2.1 allowlist" conflates two different things: (a) the `verification` string field inside `henka-record` schema properties, which describes valid verification commands but is not itself a verification command, and (b) actual verification strings in agent outputs. Schema field descriptions like `"description": "e.g. git log --oneline -5"` in `henka-record.schema.json` are not subject to the §4.5 allowlist enforcement — they are documentation, not executable strings. However, an Evaluator reading this Should-NOT gate literally could flag a schema description that mentions a non-allowlisted command as a sprint-blocking violation. The wording needs to distinguish schema descriptions from actual executable strings.
- Recommended fix: Clarify the Should-NOT to: "MUST NOT ship a schema `description` field that cites non-allowlisted example commands. All example verification strings in schema descriptions must be drawn from allowlisted prefixes. Actual fixture JSON files that contain a `verification` key with string values must also conform to the allowlist." Or, simplify: the allowlist check applies only to fixture JSON files that contain a `verification` key — not to schema `description` prose.

**Finding 8**
- Severity: MINOR
- Category: Specificity
- Description: SC-8 requires violation.md sidecars for invalid fixtures (referenced in Technical Notes as well), but the "Files in Scope" list does not explicitly enumerate these sidecar files — it says they are "listed implicitly." The Should-NOT criterion "MUST NOT create files outside the 'Files in Scope' list" could technically block the Generator from creating violation.md sidecars if the Evaluator reads "Files in Scope" strictly. This creates a direct conflict between the Technical Notes convention and the Should-NOT gate.
- Recommended fix: Either explicitly add `tests/schemas/*/invalid/*.violation.md` to the Files in Scope list, or add a parenthetical to the Should-NOT gate: "(violation.md sidecar files in `tests/schemas/<schema>/invalid/` are implicitly in scope per the Technical Notes convention)."

**Finding 9**
- Severity: MINOR
- Category: Completeness
- Description: The spec's SC-D1-1 pass condition reads "Pass: `python -m json.tool schemas/*.schema.json` succeeds for all 11 files." The contract's SC-1 runs 11 separate `python -m json.tool` calls but does not include a glob-based single invocation. On some Python versions, `python -m json.tool` accepts only one file at a time (it reads stdin if no file or exactly one file is given; multiple files cause an error). This is not a blocking issue because 11 separate calls are unambiguous, but the spec's wording (`schemas/*.schema.json`) would fail if run literally as a single command. The contract correctly avoids this by using 11 separate calls, but this inconsistency between spec and contract could confuse a Generator reading both.
- Recommended fix: NIT — add a note in SC-1 that the glob form from the spec is illustrative; the 11 separate calls are the canonical verification. No change to pass/fail semantics needed.

**Finding 10**
- Severity: NIT
- Category: Ambiguity
- Description: SC-8 dimension 2 says "includes a comment or companion `*.violation.md` file (or a `_comment` key if JSON permits)." JSON does not permit comments — a `_comment` key is a non-standard workaround. The LLM-judge grading this criterion would need to decide whether a `_comment` key in a fixture counts as "documentation." If the Generator uses `_comment` in an invalid fixture, that key itself makes the fixture deviate from the schema in an additional undocumented way (most schemas won't allow `additionalProperties: true` with `_comment`). The "or a `_comment` key if JSON permits" clause is technically misleading.
- Recommended fix: Remove the `_comment` option and require either a `*.violation.md` sidecar file (the Technical Notes convention) or a separate `violations-index.md` in each `invalid/` directory listing all fixtures and their violation types. This removes ambiguity and aligns with the Technical Notes convention.

### SC-D1-6 adjudication (Technical Notes override request)

The Technical Notes ask the Evaluator to adjudicate whether dedicated scripts are required for all 11 schemas under SC-D1-5. **Ruling: the jsonschema one-liner interpretation is accepted.** The spec text "corresponding `scripts/validate-*.py`" is most naturally read as "the script corresponding to that schema IF one exists." Only three scripts are in scope for Sprint 1. For the eight remaining schemas, `jsonschema.validate` via a Python one-liner is the functional equivalent and satisfies the intent of SC-D1-5. Generators must NOT produce dedicated `validate-*.py` scripts for the eight remaining schemas (that would violate the Should-NOT gate against out-of-scope files). The SC-5 verification for these eight schemas must use the jsonschema one-liner pattern, and this is sufficient for a PASS.

### Required revisions (before implementation begins)

- **REV-1 (Finding 1 — BLOCKER):** Remove "SC-D1-6 partial (§5)" from SC-6's "Maps to" line. Change to "Maps to: SC-D1-5 partial (§5)." Add a note that SC-D1-6 is evaluated in Sprint 4.
- **REV-2 (Finding 2 — BLOCKER):** Replace `ls ... | wc -l` in SC-5's Full pass condition with a cross-platform Python-based file-count check. The replacement must cover all 11 schemas and be runnable via `uv run python` on both Windows and Linux.
- **REV-3 (Finding 3 — MAJOR):** Either add the three hardcoded invalid fixture filenames to the "Files in Scope" list (requiring the Generator to produce them with those exact names), or rewrite SC-6's invalid-path invocations to discover filenames dynamically.
- **REV-4 (Finding 4 — MAJOR):** Replace SC-5's "illustrative" verification with a single exhaustive command (or a small self-contained script) that checks all 11 schemas deterministically. The pass condition must be mechanically executable by the Evaluator with a single command.
- **REV-5 (Finding 5 — MAJOR):** Add a contract constraint requiring all v2-required fields in `henka-record.schema.json` to be defined inline (no `$ref` for `fourM_axis`, `change_origin`, `andon_signal`, `evidence`, `yokoten` properties). This makes SC-2's verification one-liner reliable.
- **REV-6 (Finding 7 — MINOR, recommended):** Clarify the Should-NOT gate distinguishing schema `description` prose from executable `verification` strings in fixture JSON files.
- **REV-7 (Finding 8 — MINOR, recommended):** Explicitly add `tests/schemas/*/invalid/*.violation.md` to the Files in Scope list, or carve them out from the Should-NOT gate's file-scope restriction.

---

## Generator Revision (Round 2)

**Date:** 2026-05-07
**Addressed:** REV-1, REV-2, REV-3, REV-4, REV-5, REV-6, REV-7 (and Finding 6 / Finding 10)

### Summary of changes

- **REV-1:** SC-6 "Maps to" line changed to "SC-D1-5 partial (§5)" only; added explicit note that SC-D1-6 is deferred to Sprint 4.
- **REV-2 + REV-4:** SC-5 verification completely replaced with a single self-contained `python -c "..."` multi-line invocation that (a) checks fixture counts (≥3 valid, ≥3 invalid) for all 11 schemas, (b) runs dedicated validator scripts for `council-config`, `henka-record`, `decision-log-entry`, (c) uses `jsonschema.validate` for the 8 generic schemas, (d) asserts valid fixtures pass and invalid fixtures fail, (e) prints `ALL PASS` and exits 0 on full success. Works on Windows PowerShell and POSIX Bash via `python` or `uv run python`.
- **REV-3:** Added "Required-name fixture files" subsection to Files in Scope listing the six exact filenames referenced in SC-6 (`example-01.json` for each of the three dedicated-validator schemas; `missing-required.json`, `missing-fourm-axis.json`, `missing-reversibility.json` for their respective invalid directories). Generator is now contractually bound to produce these filenames.
- **REV-5:** Added two new Should-NOT gates requiring v2-required fields in `henka-record.schema.json` (`fourM_axis`, `change_origin`, `andon_signal`, `evidence`/items, `yokoten`) and `decision-log-entry.schema.json` (`reversibility`, `effective_autonomy_at_decision`, `nemawashi_walkthrough_version`, `andon_resolution`) to be defined inline — no `$ref` for these specific properties.
- **REV-6:** Rewrote the Should-NOT gate on the `verification` allowlist to explicitly distinguish schema `description` prose (not gated) from `verification` key values in fixture JSON files (gated). Old wording conflated the two.
- **REV-7:** Added "Violation sidecar files" subsection to Files in Scope explicitly listing `tests/schemas/<schema>/invalid/*.violation.md` as a recognized scope element. Updated the Should-NOT file-scope gate to include a parenthetical confirming sidecars are in scope. Updated Technical Notes to note the explicit scope listing.
- **Finding 6:** Added `$schema` declaration check to SC-1's verification (a new `python -c` block that asserts all 11 schemas carry `"$schema": "http://json-schema.org/draft-07/schema#"` and exits 0 only if all pass). Also added a corresponding Should-NOT gate ("MUST NOT ship a schema that lacks the `$schema` declaration").
- **Finding 9:** Added a note to SC-1 that the glob form from the spec is illustrative; the 11 separate `python -m json.tool` calls are the canonical verification.
- **Finding 10:** SC-8 dimension 2 rewritten to require either a `*.violation.md` sidecar or a `violations-index.md` per `invalid/` directory. Removed the `_comment` JSON key option entirely.

### Items NOT addressed (and why)

- **Finding 9 (MINOR — NIT):** A note was added to SC-1 (per the recommended fix) addressing the glob-form discrepancy. No semantic change to pass/fail criteria was needed.

---

## Evaluator Review (Round 2)

**Reviewer:** Evaluator subagent
**Date:** 2026-05-07
**Status: APPROVED**

### Verification of Round 1 revisions

- REV-1: ADDRESSED — SC-6 “Maps to” now reads “SC-D1-5 partial (§5)” only; an explicit note at the end of SC-6 states that SC-D1-6 (append script rejection) is deferred to Sprint 4 and is NOT evaluated here.
- REV-2 + REV-4: ADDRESSED — SC-5 verification is now a single self-contained multi-line `python -c` invocation that covers all 11 schemas (3 via dedicated validator scripts using `subprocess.run`, 8 via `jsonschema.validate`), checks both valid and invalid fixture counts (≥3 each), asserts valid fixtures pass and invalid fixtures fail, and exits 0 printing `ALL PASS` on full success. Uses only `glob`, `json`, `subprocess`, `pathlib`, and `jsonschema` — all cross-platform; no POSIX-only shell idioms remain.
- REV-3: ADDRESSED — A “Required-name fixture files” subsection was added to Files in Scope listing all 6 exact filenames: `example-01.json` for the three dedicated-validator valid fixtures and `missing-required.json`, `missing-fourm-axis.json`, `missing-reversibility.json` for their respective invalid directories. The Generator is now contractually bound to produce these exact names.
- REV-5: ADDRESSED — A new Should-NOT gate explicitly prohibits `$ref` indirection for the 5 named properties in `henka-record.schema.json` (`fourM_axis`, `change_origin`, `andon_signal`, `evidence`/items, `yokoten`) and the 4 named properties in `decision-log-entry.schema.json` (`reversibility`, `effective_autonomy_at_decision`, `nemawashi_walkthrough_version`, `andon_resolution`). Both schemas are covered, making SC-2 and SC-3 one-liners reliable.
- REV-6: ADDRESSED — The Should-NOT verification-allowlist gate now explicitly distinguishes schema `description` prose in `.schema.json` files (not gated) from the `verification` key’s actual string values inside fixture JSON files (gated). The wording is unambiguous and no longer conflates documentation with executable strings.
- REV-7: ADDRESSED — A “Violation sidecar files” subsection was added to Files in Scope explicitly listing `tests/schemas/<schema>/invalid/*.violation.md`. The Should-NOT file-scope gate was updated with a parenthetical confirming sidecar files are in scope and may be created freely. The conflict between the Technical Notes convention and the Should-NOT gate is resolved.
- Finding 6 (optional): ADDRESSED — SC-1 now includes a `python -c` block that checks all 11 schemas for `"$schema": "http://json-schema.org/draft-07/schema#"`, exits 0 printing `ALL PASS` on success. A corresponding Should-NOT gate was added: “MUST NOT ship a schema that lacks the `$schema` declaration.”
- Finding 10 (optional): ADDRESSED — SC-8 dimension 2 now requires either a `*.violation.md` sidecar or a `violations-index.md` per `invalid/` directory. The `_comment` JSON key option has been explicitly prohibited with a justification note.

### New findings (only if any)

None. Spot checks performed:

- Weight totals verified: SC-1 through SC-6 deterministic = 15+12+10+8+15+10 = 70%; SC-7 through SC-9 LLM-judge = 15+10+5 = 30%; grand total = 100%.
- The `\$schema` in SC-1’s `python -c` block is a markdown escape artifact. Python interprets `'\$schema'` as `'$schema'` (backslash has no effect on `$` in a Python string literal), so the `dict.get()` lookup is correct.
- SC-5’s `subprocess.run(['python', script, f])` uses list form (no shell interpretation) and is cross-platform on both Windows and POSIX.
- SC-1’s `Draft7Validator.check_schema(json.load(open(f)))` uses bare `open()` without explicit encoding — a minor inconsistency with SC-5’s `encoding='utf-8'`. JSON schema files are typically ASCII-safe so this is not a BLOCKER.

### Approval rationale

The contract is now mechanically verifiable end-to-end. Both round-1 BLOCKERs are resolved: SC-6 no longer maps to the out-of-scope SC-D1-6, and SC-5 provides a single exhaustive cross-platform Python command that checks all 22 fixture directories with a binary exit code. All three MAJORs are resolved: hardcoded fixture filenames are contractually required deliverables with exact names in Files in Scope (REV-3), v2-required fields in both revised schemas are gated against `$ref` indirection with explicit property lists for both schemas (REV-5), and the verification-allowlist Should-NOT gate unambiguously scopes only to `verification` key string values in fixture JSON files, not to schema description prose (REV-6). File scope is unambiguous: violation sidecar files are explicitly in scope, removing any conflict with the file-scope Should-NOT gate (REV-7). The optional improvements (Finding 6 `$schema` declaration verification and Should-NOT gate; Finding 10 `_comment` prohibition) were both addressed, further strengthening the contract. Weight totals sum correctly to 100%. No new blockers were introduced by the revisions. The contract is approved and ready for Generator implementation.
