# Sprint 04 Contract — S2 Core Agents + State Files

## Scope

Sprint 4 ships the four Python scripts that operationalize sprint 1's schemas and sprint 2's agent contracts: two append-on-validate scripts (`append-henka.py`, `append-decision.py`) that enforce the append-only protocol for the two highest-traffic JSONL logs, a classify-and-return evidence helper (`compute-evidence-class.py`), and a state-file writer (`update-effective-autonomy.py`) that maintains `trigger_history` append semantics. Additionally, this sprint validates — via grep-based deterministic checks — that the three existing agent markdown files (`scope-guardian.md`, `henkaten-detector.md`, `retrospective.md`) already contain the runtime-required behavioral content specified in D2. A temp-dir fixture test verifies the effective-autonomy state-write path end-to-end. No `.council/` directory is created in the project during this sprint; all write-path tests use isolated temporary directories.

---

## Files in Scope

**New Python scripts (4 files):**
- `scripts/append-henka.py` — validates JSON input against `schemas/henka-record.schema.json`, appends one line to `.council/henka-register.jsonl`, calls `git add` on the file; exits 0 on success, non-zero on validation or write failure. CLI: reads JSON from stdin OR `--file <path>`. **[NEW]**
- `scripts/append-decision.py` — validates against `schemas/decision-log-entry.schema.json`, appends to `.council/decision-log.jsonl`, calls `git add`; same exit-code semantics. CLI: reads JSON from stdin OR `--file <path>`. **[NEW]**
- `scripts/compute-evidence-class.py` — classifies an evidence claim as `observed`, `inferred`, or `speculative` based on input characteristics (§4); reads a JSON-encoded evidence claim from stdin or `--claim <json-string>`, prints the class to stdout, exits 0. **[NEW]**
- `scripts/update-effective-autonomy.py` — reads `.council/state/effective-autonomy.json` if present (idempotent merge), updates `level`/`reason`/`last_change`, appends one entry to `trigger_history`, validates the final state against `schemas/effective-autonomy.schema.json`, then writes. CLI: `--level <int>` (required), `--reason <str>` (required), `--trigger-type <enum-value>` (required), `--from-level <int>` (required), `--file <path>` (default: `.council/state/effective-autonomy.json`). Exits 0 on success, non-zero on validation failure. **[NEW]**

**New test fixture (1 file):**
- `tests/scripts/test-update-effective-autonomy.py` — self-contained pytest-style or plain-Python test; uses a `tempfile.TemporaryDirectory` (not `.council/`); starts from a level-4 baseline, calls `update-effective-autonomy.py` via `subprocess.run` with a simulated trigger, reads the output file, validates against the schema, asserts `trigger_history` length == 1. Exits 0 on full pass. **[NEW]**

**Existing agent files validated in-place (3 files):**
- `agents/scope-guardian.md` — must pass D2 frontmatter check and contain exact-string-matching behavioral content (§7.3) **[VALIDATED-EXISTING]**
- `agents/henkaten-detector.md` — must pass D2 frontmatter check and document 4M + change_origin + scheduled-vs-unscheduled suppression (§7.4, §6.7, A3) **[VALIDATED-EXISTING]**
- `agents/retrospective.md` — must pass D2 frontmatter check and contain a production-ready `mini` mode section (pdca/jishuken modes may be present or deferred to S6) (§7.5) **[VALIDATED-EXISTING]**

---

## Success Criteria

### Deterministic (weights sum to 68%)

**SC-1 [weight: 8%] — All 4 new Python scripts exist at their declared paths and their syntax is valid**

Input: check file existence and parse each script with `ast.parse`.

Verification:
```python
python -c "
import pathlib, ast, sys
scripts = [
    'scripts/append-henka.py',
    'scripts/append-decision.py',
    'scripts/compute-evidence-class.py',
    'scripts/update-effective-autonomy.py',
]
errors = []
for s in scripts:
    p = pathlib.Path(s)
    if not p.exists():
        errors.append(f'MISSING: {s}')
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR in {s}: {e}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL PRESENT AND VALID SYNTAX')
"
```

Pass condition: script prints `ALL PRESENT AND VALID SYNTAX` and exits 0.

Maps to: §4, §5.3, sprints.json S2 features

---

**SC-2 [weight: 8%] — `append-henka.py` validates and appends a valid fixture, and rejects an invalid fixture without appending**

Input: pipe `tests/schemas/henka-record/valid/example-01.json` to `append-henka.py` targeting a temp file; then pipe `tests/schemas/henka-record/invalid/missing-fourm-axis.json` and assert non-zero exit with no append.

Verification:
```python
python -c "
import subprocess, pathlib, tempfile, sys, json

valid_fixture = 'tests/schemas/henka-record/valid/example-01.json'
invalid_fixture = 'tests/schemas/henka-record/invalid/missing-fourm-axis.json'
script = 'scripts/append-henka.py'

errors = []

with tempfile.TemporaryDirectory() as tmpdir:
    out_file = pathlib.Path(tmpdir) / 'henka-register.jsonl'
    # Test 1: valid fixture -> exit 0 and file appended
    r = subprocess.run(
        ['python', script, '--file', valid_fixture, '--output', out_file],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        errors.append(f'VALID fixture rejected (exit {r.returncode}): {r.stderr.strip()}')
    elif not out_file.exists() or out_file.stat().st_size == 0:
        errors.append('VALID fixture: output file not created or empty after append')
    else:
        line = out_file.read_text(encoding='utf-8').strip()
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f'VALID fixture: appended line is not valid JSON: {e}')

    # Test 2: invalid fixture -> exit non-zero and no new content appended
    size_before = out_file.stat().st_size if out_file.exists() else 0
    r2 = subprocess.run(
        ['python', script, '--file', invalid_fixture, '--output', out_file],
        capture_output=True, text=True
    )
    if r2.returncode == 0:
        errors.append('INVALID fixture unexpectedly accepted (exit 0)')
    size_after = out_file.stat().st_size if out_file.exists() else 0
    if size_after != size_before:
        errors.append(f'INVALID fixture: output file grew after rejection ({size_before} -> {size_after} bytes)')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Note: The `--output` flag is required for test isolation (prevents writes to `.council/` during evaluation). The script's default output path (when `--output` is absent) is `.council/henka-register.jsonl`. During evaluation, `--output` overrides the target path; `git add` is skipped when using `--output` with a non-`.council/` path, OR the script attempts `git add` and exits gracefully if the path is not tracked. Both behaviors are acceptable — the key requirement is that `git add` is called when appending to the canonical `.council/henka-register.jsonl` path.

Maps to: §4, §5.3, R1/R2/R8

---

**SC-3 [weight: 8%] — `append-decision.py` validates and appends a valid fixture, and rejects an invalid fixture without appending**

Input: pipe `tests/schemas/decision-log-entry/valid/example-01.json` to `append-decision.py` targeting a temp file; then pipe `tests/schemas/decision-log-entry/invalid/missing-reversibility.json` and assert non-zero exit.

Verification:
```python
python -c "
import subprocess, pathlib, tempfile, sys, json

valid_fixture = 'tests/schemas/decision-log-entry/valid/example-01.json'
invalid_fixture = 'tests/schemas/decision-log-entry/invalid/missing-reversibility.json'
script = 'scripts/append-decision.py'

errors = []

with tempfile.TemporaryDirectory() as tmpdir:
    out_file = pathlib.Path(tmpdir) / 'decision-log.jsonl'
    # Test 1: valid fixture -> exit 0 and file appended
    r = subprocess.run(
        ['python', script, '--file', valid_fixture, '--output', out_file],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        errors.append(f'VALID fixture rejected (exit {r.returncode}): {r.stderr.strip()}')
    elif not out_file.exists() or out_file.stat().st_size == 0:
        errors.append('VALID fixture: output file not created or empty after append')
    else:
        line = out_file.read_text(encoding='utf-8').strip()
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f'VALID fixture: appended line is not valid JSON: {e}')

    # Test 2: invalid fixture -> exit non-zero and no new content
    size_before = out_file.stat().st_size if out_file.exists() else 0
    r2 = subprocess.run(
        ['python', script, '--file', invalid_fixture, '--output', out_file],
        capture_output=True, text=True
    )
    if r2.returncode == 0:
        errors.append('INVALID fixture unexpectedly accepted (exit 0)')
    size_after = out_file.stat().st_size if out_file.exists() else 0
    if size_after != size_before:
        errors.append(f'INVALID fixture: output file grew after rejection ({size_before} -> {size_after} bytes)')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Note: Same `--output` isolation semantics as SC-2. Default path when `--output` is absent is `.council/decision-log.jsonl`.

Maps to: §4, §5.3, R3/R5/R9/R10

---

**SC-4 [weight: 8%] — `compute-evidence-class.py` returns a valid class string for representative inputs**

Input: invoke the script with four representative evidence claims and assert it prints one of `observed`, `inferred`, or `speculative` for each; additionally assert that `observed` is NOT returned for a claim that has no `verification` field.

Note on `evidence_class_hint`: this is a test-only advisory field that `compute-evidence-class.py` MAY use as a classification signal but is not required to honour. If the script ignores it entirely, it must still produce a valid class based on the presence of `verification` and/or `confidence` alone. `evidence_class_hint` does not appear in any schema and carries no schema-validation weight.

Note on `confidence`: `compute-evidence-class.py` accepts `confidence` as an integer (1–5) in its stdin/`--claim` input format. This is a private input convention for the classification script; it is NOT a henka-record field. The henka-record schema defines `confidence` as a string enum (`"high"`, `"medium"`, `"low"`). There is no conflict: the classification script's input is not a henka-record.

Verification:
```python
python -c "
import subprocess, sys, json

script = 'scripts/compute-evidence-class.py'
VALID_CLASSES = {'observed', 'inferred', 'speculative'}

# Test claims: (claim dict, expected class or set of acceptable classes)
test_cases = [
    # Claim with a verification command -> must be 'observed'
    (
        json.dumps({'evidence_class_hint': 'observed', 'verification': 'git log --oneline -5', 'confidence': 5}),
        {'observed'}
    ),
    # Claim with no verification, medium confidence -> 'inferred' or 'speculative'
    (
        json.dumps({'evidence_class_hint': 'inferred', 'confidence': 3}),
        {'inferred', 'speculative'}
    ),
    # Claim with no verification, low confidence -> 'speculative' only
    (
        json.dumps({'evidence_class_hint': 'speculative', 'confidence': 1}),
        {'speculative'}
    ),
    # Negative test: no verification key present -> must NOT be 'observed'
    (
        json.dumps({'confidence': 4}),
        {'inferred', 'speculative'}
    ),
]

errors = []
for claim_json, acceptable in test_cases:
    r = subprocess.run(
        ['python', script, '--claim', claim_json],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        errors.append(f'Script exited {r.returncode} for claim {claim_json!r}: {r.stderr.strip()}')
        continue
    result = r.stdout.strip()
    if result not in VALID_CLASSES:
        errors.append(f'Invalid class {result!r} (must be one of {VALID_CLASSES}) for claim {claim_json!r}')
    elif result not in acceptable:
        errors.append(f'Unexpected class {result!r} (acceptable: {acceptable}) for claim {claim_json!r}')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4, evidence-first.md (R4)

---

**SC-5 [weight: 12%] — `update-effective-autonomy.py` end-to-end fixture test: level-4 baseline, one trigger event, schema-valid output, trigger_history grows by 1**

Input: run `tests/scripts/test-update-effective-autonomy.py` directly.

Verification:
```
python tests/scripts/test-update-effective-autonomy.py
```

Pass condition: exits 0. Any assertion failure causes a non-zero exit with a descriptive error message.

The test fixture must independently verify:
1. Starting from an empty (non-existent) state file, calling the script with `--level 4` creates a file with `level: 4` and `trigger_history` length 1 (the initial trigger entry, using `--trigger-type initial`).
2. Calling the script a second time with a different level (e.g., `--level 3`) appends to `trigger_history` (length becomes 2), does NOT overwrite the previous entry.
3. The final file validates against `schemas/effective-autonomy.schema.json` using `jsonschema.Draft7Validator`.

Maps to: §9.7, R10/Q20, sprints.json "state/effective-autonomy.json initial write path verified end-to-end"

---

**SC-6 [weight: 10%] — Cross-sprint regression: all 5 previously-validated agent files still pass their frontmatter checks**

Input: re-run the sprint 2 SC-2 frontmatter check, extended to all 5 agents now in scope (adding scope-guardian, henkaten-detector, retrospective to the sprint 3 baseline of orchestrator + architect).

Verification:
```python
python -c "
import pathlib, sys, re

EXPECTED = {
    'agents/orchestrator.md':      {'tools': {'Read','Glob','Grep','Bash','Write','Task'}, 'context': 'inherit', 'level': '4'},
    'agents/architect.md':         {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/scope-guardian.md':    {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/henkaten-detector.md': {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '1'},
    'agents/retrospective.md':     {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
}

errors = []
for path, spec in EXPECTED.items():
    text = pathlib.Path(path).read_text(encoding='utf-8')
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        errors.append(f'{path}: no YAML frontmatter found'); continue
    fm = m.group(1)
    lines = fm.splitlines()
    tools_block = []
    in_tools = False
    for l in lines:
        if re.match(r'\s*tools\s*:', l, re.IGNORECASE):
            tools_block.append(l); in_tools = True
        elif in_tools:
            if re.match(r'\s{2,}', l): tools_block.append(l)
            else: break
    tools_text = '\n'.join(tools_block)
    declared = set(re.findall(r'Read|Glob|Grep|Bash|Write|Task', tools_text))
    if declared != spec['tools']:
        errors.append(f'{path}: tools={declared}, expected={spec[\"tools\"]}')
    ctx_line = next((l for l in lines if 'context' in l.lower()), '')
    if spec['context'] not in ctx_line:
        errors.append(f'{path}: context line does not contain \"{spec[\"context\"]}\" (got: {ctx_line!r})')
    lvl_line = next((l for l in lines if 'level' in l.lower()), '')
    if not re.search(r'level:\s*' + re.escape(spec['level']) + r'\b', lvl_line):
        errors.append(f'{path}: level line does not declare level {spec[\"level\"]} exactly (got: {lvl_line!r})')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §7.1–§7.5 (sprint 2 regression gate, extended)

---

**SC-7 [weight: 8%] — Spec-content checks on the three newly-validated agent files**

Input: grep-check that each of the three agent files contains the runtime-required content markers that distinguish them from stub documents.

Verification:
```python
python -c "
import pathlib, sys, re

errors = []

# scope-guardian.md: must reference exact-string matching behavior (§7.3)
sg = pathlib.Path('agents/scope-guardian.md').read_text(encoding='utf-8')
if not re.search(r'exact.string', sg, re.IGNORECASE):
    errors.append('agents/scope-guardian.md: missing exact-string matching reference (§7.3 requirement)')
if not re.search(r'features\.json', sg, re.IGNORECASE):
    errors.append('agents/scope-guardian.md: missing features.json reference (primary input per §7.3)')
if not re.search(r'scope.drift|scope drift', sg, re.IGNORECASE):
    errors.append('agents/scope-guardian.md: missing scope drift detection language (§7.3)')

# henkaten-detector.md: must document 4M + change_origin + suppression (§7.4, §6.7, A3)
hd = pathlib.Path('agents/henkaten-detector.md').read_text(encoding='utf-8')
for axis in ['Man', 'Machine', 'Material', 'Method']:
    if axis not in hd:
        errors.append(f'agents/henkaten-detector.md: missing 4M axis \"{axis}\" (§7.4)')
if not re.search(r'change_origin', hd):
    errors.append('agents/henkaten-detector.md: missing change_origin field documentation (§7.4, R1)')
if not re.search(r'scheduled|suppression|suppress', hd, re.IGNORECASE):
    errors.append('agents/henkaten-detector.md: missing scheduled-vs-unscheduled suppression documentation (§6.7, A3)')
if not re.search(r'active|passive', hd, re.IGNORECASE):
    errors.append('agents/henkaten-detector.md: missing active/passive change_origin values (§7.4, R1)')

# retrospective.md: must document mini mode in production-ready detail (§7.5)
retro = pathlib.Path('agents/retrospective.md').read_text(encoding='utf-8')
if not re.search(r'\bmini\b', retro, re.IGNORECASE):
    errors.append('agents/retrospective.md: missing \"mini\" mode section (§7.5 — mini mode required production-ready in S2)')
if not re.search(r'standard.work.*proposal|no.*standard.work.*proposal|standard-work proposal', retro, re.IGNORECASE):
    errors.append('agents/retrospective.md: missing standard-work proposal rule for mini mode (§7.5 — mini must be capture-only)')
if not re.search(r'sprint-\{NN\}-mini\.md|sprint.*mini\.md', retro, re.IGNORECASE):
    errors.append('agents/retrospective.md: missing output destination pattern for mini mode (expected sprint-{NN}-mini.md per §7.5)')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §7.3, §7.4, §7.5, §6.7, A3

---

**SC-8 [weight: 6%] — `tests/scripts/test-update-effective-autonomy.py` exists and has valid Python syntax; no script contains stub markers**

Input: check file existence, parse syntax, and scan all 4 new scripts + the test fixture for stub markers.

Verification:
```python
python -c "
import pathlib, ast, sys, re

all_files = [
    'scripts/append-henka.py',
    'scripts/append-decision.py',
    'scripts/compute-evidence-class.py',
    'scripts/update-effective-autonomy.py',
    'tests/scripts/test-update-effective-autonomy.py',
]
errors = []
stub_markers = ['TODO', 'PLACEHOLDER', 'TBD', 'pass  # stub', 'raise NotImplementedError']
for f in all_files:
    p = pathlib.Path(f)
    if not p.exists():
        errors.append(f'MISSING: {f}')
        continue
    text = p.read_text(encoding='utf-8')
    try:
        ast.parse(text)
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR in {f}: {e}')
    for marker in stub_markers:
        if marker in text:
            errors.append(f'{f}: contains stub marker {marker!r}')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4, §5.3

---

### LLM-as-judge (weights sum to 32%)

**SC-9 [weight: 14%] — Schema-validation strictness and error-message quality in `append-henka.py` and `append-decision.py`**

The judge reads both append scripts and scores against the following rubric dimensions:

1. **Validation before append** (§5.3, Q13): The script always calls `jsonschema.Draft7Validator.validate()` (or equivalent) before any file write. There is no code path that appends to the JSONL file without first passing schema validation. No `--skip-validation` flag or equivalent bypass exists.

2. **Meaningful error messages on rejection** (§4): When schema validation fails, the script prints the `jsonschema.ValidationError` message (or a human-readable equivalent) to `stderr`. The error message identifies the offending field path and the violated constraint — not just "validation failed". A bare `except Exception: print("error")` pattern fails this dimension.

3. **Graceful handling of malformed JSON input** (§4): If the input (from stdin or `--file`) is not parseable as JSON, the script prints a clear error message to `stderr` and exits non-zero. It does not crash with an unhandled `json.JSONDecodeError` traceback.

4. **Schema path resolution** (§4): The schema is loaded relative to the project root using `pathlib.Path(__file__).parent.parent / 'schemas' / '<schema-name>.schema.json'` (or equivalent). The path is not hard-coded as an absolute path or relative `./` string. The resolution must work correctly when the script is invoked from any working directory.

5. **`git add` call** (§5.3): The script calls `subprocess.run(['git', 'add', <output_path>])` (or equivalent) after a successful append to the canonical `.council/` path. The call is present in the code. When `--output` redirects to a non-canonical path (outside `.council/`), skipping `git add` is acceptable.

Score: PASS if all 5 dimensions satisfied; PARTIAL (50% weight credit) if 3–4 satisfied; FAIL if ≤2 satisfied.

Maps to: §4, §5.3, Q13

---

**SC-10 [weight: 10%] — State-merge semantics in `update-effective-autonomy.py`**

The judge reads `scripts/update-effective-autonomy.py` and scores against the following rubric dimensions:

1. **Merge, not clobber** (§9.7, R10/Q20): When the target file already exists, the script reads the existing JSON, merges the new `level`/`reason`/`last_change` fields into it, and then writes the result. It does NOT overwrite the existing `trigger_history` array with an empty list. Specifically: if the existing file has `trigger_history: [entry1, entry2]` and the script is called once more, the written file has `trigger_history: [entry1, entry2, entry3]`.

2. **`trigger_history` append semantics** (§9.7, R10): Each call appends exactly one new entry to `trigger_history`. The script never truncates or replaces the array. The `trigger_history` entry shape matches the `effective-autonomy.schema.json` items schema (has `trigger_type`, `timestamp`, `from_level`, `to_level` at minimum).

3. **Schema validation before write** (§9.7): The script validates the final merged state against `schemas/effective-autonomy.schema.json` using `jsonschema.Draft7Validator` (or equivalent) before writing to disk. If the merged state is invalid, the script exits non-zero and does NOT write the file.

4. **`restored_when` semantics** (§11.11, Q20): The `restored_when` field is set to `null` when the level is at or above the nominal level, and to a human-readable string describing the restoration condition when the level is below nominal. The script supports this via a `--restored-when <str>` flag or equivalent (may be optional; null default is acceptable).

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% weight credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §9.7, R10/Q20, §11.11

---

**SC-11 [weight: 8%] — Script idiom and code quality across all 4 new scripts**

The judge reads all four new Python scripts and scores against the following rubric dimensions:

1. **Type annotations** (§4): All function/method signatures carry type annotations. `def main()` functions return `int`. Helper functions annotate their parameters and return types. The scripts are not bare module-level code with no functions.

2. **Consistent CLI pattern** (§4): All four scripts use `argparse` for CLI parsing. The `--help` flag produces a usage message (standard `argparse` behavior). The stdin-or-`--file` duality (for the append scripts) and the `--claim` flag (for `compute-evidence-class.py`) are implemented via `argparse`, not `sys.argv` slicing.

3. **No hard-coded absolute paths** (§4): No script contains a hard-coded absolute path (e.g., `C:\Users\...` or `/home/...`). All schema paths are resolved relative to the script file's location or relative to a project-root detected at runtime.

4. **Clean error handling** (§4): All scripts wrap their main logic in a `try/except` block or propagate errors to a `main()` function that prints to `stderr` and returns a non-zero exit code. Unhandled exception tracebacks are not the primary error UX. Exit codes are consistent: 0 = success, 1 = runtime/validation error, 2 = usage error (following the `validate-*.py` convention from sprint 1).

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% weight credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §4, sprint 1 validator convention

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

**Gate 1 — Scripts MUST NOT write to `.council/` during evaluation; the end-to-end test MUST use a temp directory**

`.council/` does not exist in this repository. Any script that creates `.council/` or writes to it without a temp-dir override during evaluation will corrupt the repository state. The test fixture `tests/scripts/test-update-effective-autonomy.py` must use `tempfile.TemporaryDirectory` (or equivalent) and must NOT reference the literal path `.council/`.

Verification:
```python
python -c "
import pathlib, sys, re

errors = []
# Check that the test fixture does not reference '.council/' as a literal write target
test_file = pathlib.Path('tests/scripts/test-update-effective-autonomy.py')
if test_file.exists():
    text = test_file.read_text(encoding='utf-8')
    # If it references .council/ it must do so only in a comment or in a string that is not used as a path arg
    # We look for literal .council/ being passed directly without tempdir context
    if re.search(r"['\"]\.council/", text) and not re.search(r'TemporaryDirectory|tmp_path|tmpdir|mkdtemp', text, re.IGNORECASE):
        errors.append('tests/scripts/test-update-effective-autonomy.py: appears to write to .council/ without a temp directory context')
# Check that .council/ was not created by this sprint
if pathlib.Path('.council').exists():
    errors.append('GATE FAIL: .council/ directory exists — scripts must not create it during sprint 4; end-to-end tests must use tmp dirs')
if errors:
    for e in errors: print('GATE FAIL:', e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 2 — Scripts MUST NOT bypass schema validation**

The append scripts must not contain a `--skip-validation`, `--no-validate`, or equivalent flag that allows bypassing schema validation before appending.

Verification:
```python
python -c "
import pathlib, sys, re

errors = []
for script in ['scripts/append-henka.py', 'scripts/append-decision.py']:
    text = pathlib.Path(script).read_text(encoding='utf-8')
    if re.search(r'skip.validat|no.validat|bypass.validat', text, re.IGNORECASE):
        errors.append(f'GATE FAIL: {script} contains a validation-bypass flag')
    # Ensure jsonschema (or validate) is called before any write/open-for-append
    # Heuristic: the word 'jsonschema' or 'validate' must appear before any 'open' in append-write mode
    if not re.search(r'jsonschema|Draft7Validator|\.validate\(', text):
        errors.append(f'GATE FAIL: {script} does not appear to call jsonschema validation at all')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 3 — Scripts MUST resolve schema files from the project root, not hard-coded absolute paths**

Verification:
```python
python -c "
import pathlib, sys, re

errors = []
windows_abs = re.compile(r'[A-Za-z]:\\\\')
posix_abs = re.compile(r\"'/[a-z]\")
scripts = [
    'scripts/append-henka.py',
    'scripts/append-decision.py',
    'scripts/compute-evidence-class.py',
    'scripts/update-effective-autonomy.py',
]
for s in scripts:
    text = pathlib.Path(s).read_text(encoding='utf-8')
    if windows_abs.search(text):
        errors.append(f'GATE FAIL: {s} contains a hard-coded Windows absolute path')
    if posix_abs.search(text):
        errors.append(f'GATE FAIL: {s} contains a hard-coded POSIX absolute path')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 4 — Scripts MUST NOT execute `git push`, `git reset --hard`, or `rm -rf`**

Verification:
```python
python -c "
import pathlib, sys, re

forbidden = [r'git push', r'git reset --hard', r'rm -rf', r'rm -fr']
scripts = [
    'scripts/append-henka.py',
    'scripts/append-decision.py',
    'scripts/compute-evidence-class.py',
    'scripts/update-effective-autonomy.py',
]
errors = []
for s in scripts:
    text = pathlib.Path(s).read_text(encoding='utf-8')
    for pattern in forbidden:
        if re.search(pattern, text):
            errors.append(f'GATE FAIL: {s} contains forbidden operation: {pattern!r}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 5 — The three existing agent files MUST NOT be deleted or have their frontmatter stripped**

Verification:
```python
python -c "
import pathlib, sys, re

errors = []
for path in ['agents/scope-guardian.md', 'agents/henkaten-detector.md', 'agents/retrospective.md']:
    p = pathlib.Path(path)
    if not p.exists():
        errors.append(f'GATE FAIL: {path} missing — must not be deleted in sprint 4')
        continue
    text = p.read_text(encoding='utf-8')
    if not re.match(r'^---\s*\n', text):
        errors.append(f'GATE FAIL: {path} frontmatter stripped — first line must be \"---\"')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 6 — Cross-sprint scope drift: only declared sprint-4 files were added or modified since the pre-sprint baseline commit `fa4dc1e`**

This gate uses the pre-sprint baseline commit reference (not `HEAD`) to avoid the false-positive environment-contamination failure that affected Gate 5 in sprint 3. The lesson from sprint 3's eval: `git diff HEAD` cannot distinguish pre-existing uncommitted changes from generator-introduced changes. Using a commit ref eliminates this ambiguity.

Verification:
```python
python -c "
import subprocess, sys

ALLOWED_NEW = {
    'scripts/append-henka.py',
    'scripts/append-decision.py',
    'scripts/compute-evidence-class.py',
    'scripts/update-effective-autonomy.py',
    'tests/scripts/test-update-effective-autonomy.py',
    '.harness/contracts/sprint-04.md',
}
# Existing files that may be touched (e.g., for minor corrections) but not deleted:
ALLOWED_MODIFY = {
    'agents/scope-guardian.md',
    'agents/henkaten-detector.md',
    'agents/retrospective.md',
    '.harness/progress.md',
    '.harness/sprint-state.json',
}
ALLOWED_ALL = ALLOWED_NEW | ALLOWED_MODIFY

result = subprocess.run(
    ['git', 'diff', '--name-only', '--diff-filter=ACM', 'fa4dc1e..HEAD'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print('GATE FAIL: git diff command failed:', result.stderr.strip()); sys.exit(1)

changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
errors = []
for f in changed:
    if f not in ALLOWED_ALL:
        errors.append(f'GATE FAIL: unexpected file outside sprint-4 scope: {f!r}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

Pass condition: script prints `GATE PASS` and exits 0.

---

## Reference Solutions

Reference implementation sketch for **SC-9** (highest-weighted LLM-judge criterion) — expected structure for `scripts/append-henka.py`:

```python
"""Validate a henka-record JSON object and append it to .council/henka-register.jsonl.

Usage:
    python scripts/append-henka.py --file <path-to-json>
    echo '{"id": "HK-0001", ...}' | python scripts/append-henka.py

Exit codes:
    0  — validated and appended successfully
    1  — validation failure, JSON parse error, or I/O error
    2  — usage error
"""
from __future__ import annotations
import argparse
import json
import pathlib
import subprocess
import sys
from typing import Optional

import jsonschema

SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schemas" / "henka-record.schema.json"
DEFAULT_OUTPUT = pathlib.Path(".council") / "henka-register.jsonl"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(instance: dict, schema: dict) -> None:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        for err in errors:
            path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
            print(f"  [{err.validator}] at {path}: {err.message}", file=sys.stderr)
        raise jsonschema.ValidationError("Schema validation failed.")


def append_line(output_path: pathlib.Path, instance: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(instance) + "\n")


def git_add(path: pathlib.Path) -> None:
    subprocess.run(["git", "add", str(path)], check=False)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and append a henka-record.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--file", type=pathlib.Path, help="Path to JSON file to append.")
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT,
                        help="Output JSONL file (default: .council/henka-register.jsonl).")
    args = parser.parse_args(argv)

    try:
        if args.file:
            raw = args.file.read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        instance = json.loads(raw)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        schema = load_schema()
        validate(instance, schema)
    except jsonschema.ValidationError:
        print("INVALID: schema validation failed (details above).", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR loading schema: {exc}", file=sys.stderr)
        return 1

    try:
        append_line(args.output, instance)
    except OSError as exc:
        print(f"ERROR writing to {args.output}: {exc}", file=sys.stderr)
        return 1

    canonical = str(args.output).replace("\\", "/")
    if ".council/" in canonical:
        git_add(args.output)

    print(f"APPENDED: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

The key behavioral invariants shown above:
- `validate()` is always called before `append_line()` — no bypass path exists
- Errors go to `stderr` with field-level detail (`[err.validator] at <path>: <message>`)
- `git add` is called only when appending to the canonical `.council/` path
- Type annotations on all function signatures
- `argparse` for all CLI parsing
- Schema resolved relative to `__file__`, not hard-coded

---

## Out of Scope

- **Hooks** (`hooks/enforce-append-only.sh`, `hooks/enforce-reversibility.sh`, etc.) — sprint 5 (S3) deliverables.
- **`scripts/rotate-audit-log.py`** — sprint 5 (S3) deliverable.
- **`scripts/run-verification.py`** — sprint 6 (S4) deliverable.
- **Actually creating `.council/` on disk** — `.council/` is not created in this sprint; the effective-autonomy test uses a temp directory.
- **Live integration with Claude Code's PreToolUse/PostToolUse hooks** — sprint 5 (S3) territory.
- **Wire-up of these scripts into the orchestrator's Bash dispatch** — the scripts must exist and be invocable; orchestrator dispatch is sprint 6 (S4) territory.
- **`agents/qa-regression.md` and `agents/rag-source.md`** — not validated in this sprint (status: proposed, not in default fan-out per §7.6/§7.7/Q4).
- **`agents/retrospective.md` pdca and jishuken modes** — deferred to sprint 8 (S6). The mini mode section must be production-ready in sprint 4; pdca/jishuken presence is optional at this stage.
- **CI configuration** — sprint 5 (S3) deliverable.
- **`tests/fixtures/dummy-project/`** — sprint 6 (S4) deliverable.
- **`scripts/append-audit.py`** — not in sprints.json S2 features; out of scope.
- **Additional templates** (`retrospective-mini.md`, etc.) — sprint 8 (S6) deliverables.

---

## Technical Notes

**`jsonschema` dependency confirmed from sprint 1:** `scripts/validate-henka-record.py` uses `import jsonschema` and `jsonschema.Draft7Validator`. Sprint 4's append scripts inherit this dependency. The evaluation environment must have `jsonschema` ≥ 4.0 installed. The sprint 1 eval confirmed `jsonschema` was available and all verification commands ran correctly on the Windows platform — no additional install step is expected.

**`--output` flag for test isolation:** SC-2 and SC-3 require that the append scripts accept an `--output <path>` flag that redirects the append target to a temp file. This prevents `.council/` writes during evaluation. The default (when `--output` is omitted) remains `.council/henka-register.jsonl` and `.council/decision-log.jsonl` respectively. The `git add` call should be skipped or silently no-op when the output path is outside `.council/`. The reference solution in SC-9 shows the canonical implementation pattern.

**`compute-evidence-class.py` classification logic:** The spec (§4, R4) and `evidence-first.md` describe three evidence classes — `observed` (has a re-runnable verification command from the allowlist), `inferred` (reasoned from observed data, cites the observed claims it derives from), `speculative` (hypothesis not yet grounded in observation; permitted action: `log-only` only per `evidence-first.md`). The script's classification may use the presence of a `verification` key and/or an integer `confidence` threshold (1–5) as heuristics. The SC-4 test cases are intentionally permissive on the boundary between `inferred` and `speculative` for medium-confidence inputs (confidence ≥ 2), but require `speculative` for confidence-1 no-verification inputs — the key invariant is that `observed` is returned only when a `verification` command is present.

**`update-effective-autonomy.py` `trigger_history` append semantics:** The `trigger_history` array in `effective-autonomy.schema.json` is defined with a full `items` sub-schema (required: `trigger_type`, `timestamp`, `from_level`, `to_level`). The update script must produce entries that satisfy this items schema. The `trigger_type` enum values defined in the schema are: `consecutive-fail-drop`, `andon-stop-drop`, `high-risk-henkaten-drop`, `restore-autonomy`, `manual-override`, `sprint-pass-restore`, `initial`. The `--trigger-type` CLI argument must accept one of these values. If the target file does not exist, the script bootstraps it with `trigger_history: [<the-new-entry>]`.

**Schema path resolution pattern:** All four scripts should resolve their schema files using:
```python
SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schemas" / "<schema-name>.schema.json"
```
This is the same pattern used in `scripts/validate-henka-record.py` from sprint 1, confirmed working on Windows in the sprint 1 eval.

**Test fixture structure for `tests/scripts/test-update-effective-autonomy.py`:** The fixture must be a self-contained runnable Python script (not a pytest fixture requiring a test runner). It uses `subprocess.run` to invoke `update-effective-autonomy.py` — the same pattern used in the sprint 1 SC-5 fixture harness. The test exits 0 on full pass, non-zero with a descriptive message on any assertion failure.

**Cross-sprint scope drift gate uses commit `fa4dc1e`:** This is the commit that the sprint 3 evaluator identified as the post-sprint-3 harness checkpoint. The Gate 6 command is `git diff --name-only --diff-filter=ACM fa4dc1e..HEAD`, which shows only files Added, Copied, or Modified since that commit — it is immune to pre-existing working-tree state. This directly applies the lesson from sprint 3's Gate 5 false-fail.

**`retrospective.md` pdca/jishuken deferred-but-present:** Sprint 2 delivered `agents/retrospective.md` documenting all three modes. SC-7 requires only that the `mini` mode section is present and production-ready. If the file also documents `pdca` and `jishuken` mode sections (which it does, per sprint 2), that is acceptable and does not constitute scope creep. Sprint 8 will implement additional tooling for those modes.

**`.harness/sprint-state.json` in Gate 6 `ALLOWED_MODIFY`:** This file is maintained by the harness machinery (not by the Generator) and may be updated during sprint execution as context-compaction state. It is listed in Gate 6's `ALLOWED_MODIFY` set to prevent false-positive gate failures when the harness updates it mid-sprint. The Generator is not expected to modify this file; it is not listed in the sprint's Files in Scope section because it is a harness artifact, not a deliverable.

---

**Task taxonomy handoff:** Once this contract is approved by the Evaluator, a sibling `.harness/contracts/sprint-04.tasks.json` is emitted (guarded by `config.taxonomy.emit_tasks_json`, default `true`). It contains one JSON entry per criterion above — both Success Criteria and Should-NOT gates — with stable `task_id`s, `grader_type`, `weight`, `is_gate`, `verification_command`, and `rubric_dimension`. Downstream sprints (regression gate, Batch API, transcript capture, adversarial hygiene) consume that JSON; this markdown contract remains the human-readable source of truth. See `skills/sprint-contract/SKILL.md` for the schema.



## Evaluator Review

**Status: APPROVED**

### Summary
All round-1 issues have been addressed: every evidence-class use of `assumed` was replaced with `speculative`; the `confidence`-as-integer private-convention note (M1) and `evidence_class_hint` advisory note (M2) are present in SC-4; SC-4 now carries four test cases with tightened expectations (m1); SC-5 explicitly names `--level 4` then `--level 3` (m2); and `.harness/sprint-state.json` is listed in Gate 6 ALLOWED_MODIFY with an explanatory Technical Note (m3). Gate 1 regex is pre-resolved by the orchestrator empirical run (B2 closed). Weights sum to exactly 100% across 11 criteria (68% deterministic + 32% LLM-judge).

### Blockers (must fix before approval)
None.

### Major issues
None.

### Minor / nice-to-have
- SC-2/SC-3 note that both 'skip git add' and 'exit gracefully' are acceptable when `--output` redirects outside `.council/`; the dual-phrasing is harmless and does not create a grading ambiguity. No action required.
- Gate 3 POSIX-absolute-path check pattern (`/[a-z]`) will not match paths beginning with uppercase letters (e.g., `/Volumes/...`); on this Windows-native project this is an unlikely failure mode. Noted for a future regression-tightening pass, not blocking.
